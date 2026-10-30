import os
import io
import logging
import json
import uuid
import hashlib
import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone

import numpy as np
from fastapi import BackgroundTasks, FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader

from logging_config import setup_logging

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

# ---------- Config ----------
DB_PATH = os.getenv("SQLITE_PATH", "graphrag.db")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
CHAT_MODEL = os.getenv("CHAT_MODEL", "openai/gpt-4.1-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")  # runs locally, free
VECTOR_LIMIT = int(os.getenv("VECTOR_LIMIT", "8"))  # max chunks sent to the model
MAX_CHUNKS_PER_PAPER = 2
SCORE_MARGIN = float(os.getenv("SCORE_MARGIN", "0.10"))  # how far below the best chunk we still accept
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.30"))        # absolute minimum similarity
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 180
MAX_UPLOAD_MB = 25
CHAT_MAX_TOKENS = int(os.getenv("CHAT_MAX_TOKENS", "3000"))
CHAT_MAX_TOKENS_CAP = int(os.getenv("CHAT_MAX_TOKENS_CAP", "4000"))  # upper bound for the empty-reply retry
CHAT_TEMPERATURE = float(os.getenv("CHAT_TEMPERATURE", "0"))  # 0 = most repeatable answers
META_MAX_TOKENS = int(os.getenv("META_MAX_TOKENS", "4000"))  # reasoning models need room to think
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
INCLUDE_EMBEDDINGS = os.getenv("INCLUDE_EMBEDDINGS", "0") == "1"

# Prompt-size limits for the graph context (keeps requests under per-minute token limits of small tiers).
ENTITY_LIMIT = int(os.getenv("ENTITY_LIMIT", "40"))                  # entities linked to retrieved papers
SHARED_ENTITIES_LIMIT = int(os.getenv("SHARED_ENTITIES_LIMIT", "12"))  # library-wide shared entities
SHARED_ENTITY_EXAMPLES = int(os.getenv("SHARED_ENTITY_EXAMPLES", "2"))  # paper titles shown per shared entity
# Library-wide "shared entities" are dominated by vague terms that are not useful answers.
GENERIC_ENTITIES = {"machine learning", "deep learning", "neural network", "neural networks",
                    "artificial intelligence", "accuracy", "dropout"}

RELATION_BY_TYPE = {"MODEL": "USES_METHOD", "METHOD": "USES_METHOD", "DATASET": "USES_DATASET",
                    "TOPIC": "ABOUT_TOPIC", "TASK": "ABOUT_TOPIC", "METRIC": "USES_METRIC"}

# ---------- Clients ----------
# OpenRouter is used only for the chat model; embeddings are local.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")  # e.g. http://localhost:11434/v1 for Ollama
LLM_API_KEY = os.getenv("LLM_API_KEY", OPENROUTER_API_KEY) or "not-needed"
llm = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
app = FastAPI(title="Research Papers GraphRAG (SQLite)")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def db():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def placeholders(n: int) -> str:
    return ",".join("?" * n)


# ---------- In-memory vector index (rebuilt lazily after each ingest) ----------
_cache = {"matrix": None, "meta": []}
_cache_lock = threading.Lock()


def invalidate_cache():
    with _cache_lock:
        _cache["matrix"], _cache["meta"] = None, []


def load_cache():
    with _cache_lock:
        if _cache["matrix"] is not None:
            return _cache["matrix"], _cache["meta"]
        with db() as c:
            rows = c.execute(
                "SELECT c.paper_id, c.chunk_index, c.text, c.embedding, p.title, p.filename "
                "FROM chunks c JOIN papers p ON p.paper_id = c.paper_id"
            ).fetchall()
        if not rows:
            return None, []
        m = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
        m /= np.linalg.norm(m, axis=1, keepdims=True) + 1e-10
        meta = [{k: r[k] for k in ("paper_id", "chunk_index", "text", "title", "filename")} for r in rows]
        _cache["matrix"], _cache["meta"] = m, meta
        return m, meta


# ---------- Helpers ----------
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "api").lower()  # "api" (OpenRouter) or "local"
emb_client = OpenAI(api_key=OPENROUTER_API_KEY or "missing", base_url="https://openrouter.ai/api/v1")

_embedder = None
_embedder_lock = threading.Lock()


def get_embedder():
    """Local mode only: load the embedding model once (first call downloads ~2.2 GB)."""
    global _embedder
    with _embedder_lock:
        if _embedder is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading local embedding model %s ...", EMBEDDING_MODEL)
            _embedder = SentenceTransformer(EMBEDDING_MODEL)
            _embedder.max_seq_length = 512
        return _embedder


def embed(texts: list[str]) -> list[list[float]]:
    if EMBEDDING_PROVIDER == "local":
        vecs = get_embedder().encode(texts, batch_size=16, normalize_embeddings=True,
                                     show_progress_bar=False)
        return vecs.tolist()
    # API mode: embeddings go to OpenRouter, even if the chat model runs on Ollama.
    vectors = []
    for i in range(0, len(texts), 32):
        res = emb_client.embeddings.create(model=EMBEDDING_MODEL, input=texts[i:i + 32])
        vectors.extend(d.embedding for d in res.data)
    return vectors


def split_text(text: str) -> list[str]:
    text = " ".join(text.split())
    step = CHUNK_SIZE - CHUNK_OVERLAP
    return [text[i:i + CHUNK_SIZE] for i in range(0, len(text), step)]


def read_pdf(data: bytes) -> tuple[str, int]:
    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(f"[Page {n}] {p.extract_text() or ''}" for n, p in enumerate(reader.pages, 1))
        return text, len(reader.pages)
    except Exception as exc:
        raise HTTPException(400, f"Could not read PDF: {exc}")


def parse_json_loose(txt: str | None) -> dict:
    """Parse JSON even if the model wrapped it in ```fences``` or added extra text."""
    if not txt:
        raise ValueError("empty response")
    txt = txt.strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        txt = txt[4:] if txt.lower().startswith("json") else txt
    a, b = txt.find("{"), txt.rfind("}")
    if a == -1 or b == -1:
        raise ValueError("no JSON object found")
    return json.loads(txt[a:b + 1])


def extract_metadata(text: str, filename: str) -> dict:
    prompt = (
        'Return JSON only: {"title": str, "authors": [str], "year": int|null, '
        '"entities": [{"name": str, "type": "MODEL|DATASET|METHOD|METRIC|TASK|TOPIC"}]}. '
        "Do not invent authors or years. Max 35 entities.\n\nText:\n" + text[:14000]
    )
    # Try with JSON mode first, then without (some free models don't support it).
    for attempt, use_json_mode in enumerate((True, False), 1):
        try:
            kwargs = {"response_format": {"type": "json_object"}} if use_json_mode else {}
            res = llm.chat.completions.create(
                model=CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=META_MAX_TOKENS,
                **kwargs,
            )
            return parse_json_loose(res.choices[0].message.content)
        except Exception as exc:
            logger.warning("Metadata attempt %d failed for %s: %s", attempt, filename, exc)
    logger.error("Metadata extraction failed for %s; using fallback", filename)
    return {"title": filename, "authors": [], "year": None, "entities": []}


# ---------- Schema ----------
def create_indexes():
    """Create tables if missing. (Name kept so ingest_data.py keeps working.)"""
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS papers (
            paper_id TEXT PRIMARY KEY, filename TEXT, sha256 TEXT UNIQUE, title TEXT,
            authors TEXT, year INTEGER, page_count INTEGER, uploaded_at TEXT);
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, paper_id TEXT NOT NULL,
            chunk_index INTEGER, text TEXT, embedding BLOB);
        CREATE INDEX IF NOT EXISTS idx_chunks_paper ON chunks(paper_id);
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT, canonical_name TEXT UNIQUE, name TEXT, type TEXT);
        CREATE TABLE IF NOT EXISTS edges (
            paper_id TEXT NOT NULL, entity_id INTEGER NOT NULL, relation TEXT,
            PRIMARY KEY (paper_id, entity_id));
        CREATE INDEX IF NOT EXISTS idx_edges_entity ON edges(entity_id);
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT,
            content TEXT, created_at TEXT);
        CREATE INDEX IF NOT EXISTS idx_msgs_session ON chat_messages(session_id, id);
        CREATE TABLE IF NOT EXISTS memory_summaries (
            session_id TEXT PRIMARY KEY, summary TEXT, updated_at TEXT);
        """)
        cols = [r["name"] for r in c.execute("PRAGMA table_info(chat_messages)")]
        if "is_summarized" not in cols:  # migrate databases created before memory compaction existed
            c.execute("ALTER TABLE chat_messages ADD COLUMN is_summarized INTEGER NOT NULL DEFAULT 0")


def export_chunks_json(paper_id: str, name: str, title: str, pieces: list[str], vectors: list[list[float]]):
    """Write one JSON file per paper showing every chunk and its overlap."""
    step = CHUNK_SIZE - CHUNK_OVERLAP
    items = []
    for i, (p, v) in enumerate(zip(pieces, vectors)):
        item = {
            "chunk_index": i,
            "start_char": i * step,
            "end_char": i * step + len(p),
            "length": len(p),
            "overlap_with_previous": p[:CHUNK_OVERLAP] if i > 0 else "",
            "overlap_with_next": p[-CHUNK_OVERLAP:] if i < len(pieces) - 1 else "",
            "text": p,
            "embedding_dim": len(v),
            "embedding_preview": [round(x, 5) for x in v[:5]],
        }
        if INCLUDE_EMBEDDINGS:
            item["embedding"] = v
        items.append(item)

    doc = {
        "paper_id": paper_id, "filename": name, "title": title,
        "chunk_size": CHUNK_SIZE, "chunk_overlap": CHUNK_OVERLAP,
        "total_chunks": len(pieces), "embedding_model": EMBEDDING_MODEL,
        "chunks": items,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{Path(name).stem}.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Chunks JSON written: %s", path)


# ---------- Ingest ----------
def ingest_pdf(name: str, data: bytes) -> dict:
    if not name.lower().endswith(".pdf"):
        raise HTTPException(400, "Upload a PDF file.")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_MB} MB.")

    digest = hashlib.sha256(data).hexdigest()
    logger.info("Upload received: %s (%.1f MB)", name, len(data) / 1024 / 1024)
    with db() as c:
        existing = c.execute("SELECT paper_id, title FROM papers WHERE sha256=?", (digest,)).fetchone()
    if existing:
        logger.info("Duplicate upload skipped: %s", name)
        return {"paper_id": existing["paper_id"], "title": existing["title"], "already_exists": True}

    text, page_count = read_pdf(data)
    if len(text.strip()) < 80:
        raise HTTPException(422, "No extractable text. If this is a scanned PDF, run OCR first.")

    meta = extract_metadata(text, name)
    paper_id = str(uuid.uuid4())
    title = str(meta.get("title") or name)
    pieces = split_text(text)
    vectors = embed(pieces)  # do the slow API work before opening the write transaction

    with db() as c:
        c.execute("INSERT INTO papers VALUES (?,?,?,?,?,?,?,?)",
                  (paper_id, name, digest, title, json.dumps(meta.get("authors") or []),
                   meta.get("year"), page_count, now()))
        for ent in meta.get("entities") or []:
            if isinstance(ent, dict) and str(ent.get("name") or "").strip():
                ent_name = ent["name"].strip()
                etype = str(ent.get("type") or "CONCEPT").upper()
                c.execute("INSERT OR IGNORE INTO entities (canonical_name, name, type) VALUES (?,?,?)",
                          (ent_name.lower(), ent_name, etype))
                eid = c.execute("SELECT id FROM entities WHERE canonical_name=?", (ent_name.lower(),)).fetchone()["id"]
                c.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?)",
                          (paper_id, eid, RELATION_BY_TYPE.get(etype, "MENTIONS")))
        c.executemany(
            "INSERT INTO chunks (paper_id, chunk_index, text, embedding) VALUES (?,?,?,?)",
            [(paper_id, i, p, np.asarray(v, dtype=np.float32).tobytes())
             for i, (p, v) in enumerate(zip(pieces, vectors))])
    invalidate_cache()
    try:
        export_chunks_json(paper_id, name, title, pieces, vectors)
    except Exception:
        logger.exception("Could not write chunks JSON for %s", name)
    logger.info("Ingested '%s': %d pages, %d chunks, %d entities", title, page_count, len(pieces),
                len(meta.get("entities") or []))
    return {"paper_id": paper_id, "title": title, "chunks_created": len(pieces), "already_exists": False}


@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    return ingest_pdf(file.filename or "paper.pdf", await file.read())


# ---------- Retrieval ----------
def retrieve(question: str):
    matrix, meta = load_cache()
    if matrix is None:
        return "EXCERPTS:\n(none)\n\nRELATED ENTITIES:\n(none)", []

    q = np.asarray(embed([question])[0], dtype=np.float32)
    q /= np.linalg.norm(q) + 1e-10
    scores = matrix @ q
    best = float(scores.max())
    # The best chunk always passes; the rest must be close to it and above the absolute minimum.
    cutoff = min(max(best - SCORE_MARGIN, MIN_SCORE), best)
    # Take the best chunks but at most MAX_CHUNKS_PER_PAPER per paper, so one paper can't crowd out the rest.
    top, per_paper = [], {}
    for i in np.argsort(-scores)[:80]:
        if scores[i] < cutoff:
            break  # sorted descending, so everything after is weaker
        pid = meta[i]["paper_id"]
        if per_paper.get(pid, 0) >= MAX_CHUNKS_PER_PAPER:
            continue
        per_paper[pid] = per_paper.get(pid, 0) + 1
        top.append(i)
        if len(top) >= VECTOR_LIMIT:
            break
    hits = [{**meta[i], "score": float(scores[i])} for i in top]

    # Graph step 1: entities linked to the retrieved papers.
    # Graph step 2: neighbouring papers that share entities with them (ranked by overlap).
    # All queries have an explicit ORDER BY so the prompt is the same on every run.
    paper_ids = list({h["paper_id"] for h in hits})
    ph = placeholders(len(paper_ids))
    with db() as c:
        ents = c.execute(
            f"SELECT DISTINCT e.name, e.type, ed.relation FROM edges ed JOIN entities e ON e.id=ed.entity_id "
            f"WHERE ed.paper_id IN ({ph}) ORDER BY e.name LIMIT {ENTITY_LIMIT}", paper_ids).fetchall()
        neighbours = c.execute(
            f"SELECT p.title, COUNT(*) AS shared FROM edges e1 "
            f"JOIN edges e2 ON e1.entity_id=e2.entity_id AND e2.paper_id != e1.paper_id "
            f"JOIN papers p ON p.paper_id=e2.paper_id "
            f"WHERE e1.paper_id IN ({ph}) AND e2.paper_id NOT IN ({ph}) "
            f"GROUP BY p.paper_id ORDER BY shared DESC, p.title LIMIT 3", paper_ids + paper_ids).fetchall()

        # Fetch more than we need, then drop vague terms and metrics in Python.
        shared_rows = c.execute(
            "SELECT e.name, e.type, COUNT(*) AS n, GROUP_CONCAT(p.title, ' || ') AS papers "
            "FROM entities e JOIN edges ed ON ed.entity_id=e.id JOIN papers p ON p.paper_id=ed.paper_id "
            "GROUP BY e.id HAVING n > 1 ORDER BY n DESC, e.name LIMIT 80").fetchall()

    shared = [r for r in shared_rows
              if r["name"].strip().lower() not in GENERIC_ENTITIES and (r["type"] or "").upper() != "METRIC"]
    shared = shared[:SHARED_ENTITIES_LIMIT]
    shared_text = "\n".join(
        f"- {r['name']} ({r['type']}) appears in {r['n']} papers, e.g. " +
        "; ".join(sorted((r["papers"] or "").split(" || "))[:SHARED_ENTITY_EXAMPLES]) for r in shared)
    graph_text = "\n".join(f"- {e['name']} ({e['type']}, {e['relation']})" for e in ents)
    neighbour_text = "\n".join(f"- {n['title']} (shares {n['shared']} entities)" for n in neighbours)
    chunk_text = "\n\n".join(f"[Source: {h['title']}, chunk {h['chunk_index']}]\n{h['text']}" for h in hits)
    context = (f"EXCERPTS:\n{chunk_text}\n\nRELATED ENTITIES:\n{graph_text or '(none)'}"
               f"\n\nRELATED PAPERS (shared entities):\n{neighbour_text or '(none)'}"
               f"\n\nENTITIES SHARED BY MULTIPLE PAPERS (whole library):\n{shared_text or '(none)'}")
    return context, hits


# ---------- Conversation memory ----------
# Rule: once a session has >= COMPACT_AT unsummarized messages, summarize everything except the
# newest KEEP_VERBATIM messages. Summarized messages are marked is_summarized=1, never deleted.
COMPACT_AT = 8
KEEP_VERBATIM = 2
_compact_lock = threading.Lock()


def compact_memory(session_id: str):
    with _compact_lock:
        with db() as c:
            rows = c.execute("SELECT id, role, content FROM chat_messages "
                             "WHERE session_id=? AND is_summarized=0 ORDER BY id", (session_id,)).fetchall()
            if len(rows) < COMPACT_AT:
                return
            old = rows[:-KEEP_VERBATIM]
            prev = c.execute("SELECT summary FROM memory_summaries WHERE session_id=?",
                             (session_id,)).fetchone()
        transcript = "\n".join(f"{r['role'].upper()}: {r['content']}" for r in old)
        prompt = (
            "Update the running summary of a conversation between a user and a research-paper assistant. "
            "Keep it short (under 200 words). Preserve the user's goals, the papers and topics discussed, "
            "and any preferences. Do not add facts that are not in the text.\n\n"
            f"PREVIOUS SUMMARY:\n{prev['summary'] if prev else '(none)'}\n\n"
            f"NEW MESSAGES TO FOLD IN:\n{transcript}\n\nUpdated summary:")
        summary = ""
        try:
            for attempt in (1, 2):
                res = llm.chat.completions.create(
                    model=CHAT_MODEL, messages=[{"role": "user", "content": prompt}],
                    temperature=0, max_tokens=CHAT_MAX_TOKENS * attempt)
                summary = (res.choices[0].message.content or "").strip()
                if summary:
                    break
        except Exception:
            logger.exception("Memory summarization failed; will retry on a later message")
            return
        if not summary:
            logger.warning("Empty memory summary; will retry on a later message")
            return
        with db() as c:
            c.execute("INSERT INTO memory_summaries (session_id, summary, updated_at) VALUES (?,?,?) "
                      "ON CONFLICT(session_id) DO UPDATE SET summary=excluded.summary, updated_at=excluded.updated_at",
                      (session_id, summary, now()))
            c.executemany("UPDATE chat_messages SET is_summarized=1 WHERE id=?", [(r["id"],) for r in old])
        logger.info("Memory compacted [%s]: %d messages summarized, %d kept", session_id[:8], len(old), KEEP_VERBATIM)


# ---------- Chat ----------
class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None


@app.post("/api/chat")
def chat(req: ChatRequest, background: BackgroundTasks):
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "Question cannot be empty.")
    session_id = req.session_id or str(uuid.uuid4())

    with db() as c:
        rows = c.execute("SELECT role, content FROM chat_messages WHERE session_id=? AND is_summarized=0 "
                         "ORDER BY id", (session_id,)).fetchall()
        mem = c.execute("SELECT summary FROM memory_summaries WHERE session_id=?", (session_id,)).fetchone()
    recent = [{"role": r["role"], "content": r["content"]} for r in rows]
    memory_text = (mem["summary"] if mem else "") or ""

    logger.info("Chat [%s]: %s", session_id[:8], question[:100])
    try:
        context, hits = retrieve(question)
    except Exception as exc:
        logger.exception("Retrieval failed")
        raise HTTPException(500, f"Retrieval failed: {exc}")
    logger.info("Retrieved %d chunks", len(hits))

    system = ("You are a research-paper assistant. Answer only from the context below. "
              "The EXCERPTS are only a sample of the library, so never conclude that something is absent from "
              "other papers just because it is missing from the excerpts. The graph sections (RELATED ENTITIES, "
              "RELATED PAPERS, ENTITIES SHARED BY MULTIPLE PAPERS) are library-wide facts you may use, "
              "especially for questions about overlaps between papers. "
              "If the evidence is insufficient, say so. Cite excerpts as [Paper title, chunk N]. "
              "Write answers in Markdown. Use a table only when asked to compare; put citations inside the cell text, "
              "never in an extra column.\n\n" + context
              + (f"\n\nCONVERSATION SUMMARY (for continuity only; NOT evidence about the papers):\n{memory_text}"
                 if memory_text else ""))
    answer = ""
    try:
        for attempt in (1, 2):
            res = llm.chat.completions.create(
                model=CHAT_MODEL,
                messages=[{"role": "system", "content": system}, *recent, {"role": "user", "content": question}],
                temperature=CHAT_TEMPERATURE,
                # retry with more room if the reply came back empty, but never above the cap
                max_tokens=min(CHAT_MAX_TOKENS * attempt, max(CHAT_MAX_TOKENS, CHAT_MAX_TOKENS_CAP)),
            )
            answer = (res.choices[0].message.content or "").strip()
            if answer:
                break
            logger.warning("Empty answer from %s (attempt %d)", CHAT_MODEL, attempt)
    except Exception as exc:
        logger.exception("LLM request failed")
        raise HTTPException(502, f"LLM request failed: {exc}")
    if not answer:
        answer = ("The model returned an empty reply (common with free 'thinking' models). "
                  "Please ask again, or switch CHAT_MODEL in .env.")

    with db() as c:
        c.executemany("INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                      [(session_id, "user", question, now()), (session_id, "assistant", answer, now())])
    background.add_task(compact_memory, session_id)  # runs after the response is sent
    return {
        "session_id": session_id,
        "answer": answer,
        "sources": [{"paper_title": h["title"], "filename": h["filename"],
                     "chunk_index": h["chunk_index"], "score": round(h["score"], 4)} for h in hits],
    }


# ---------- Misc ----------
@app.on_event("startup")
def startup():
    logger.info("Starting app. chat=%s embeddings=%s db=%s", CHAT_MODEL, EMBEDDING_MODEL, DB_PATH)
    create_indexes()


@app.get("/")
def home():
    return FileResponse("index.html")


@app.get("/api/papers")
def list_papers():
    with db() as c:
        rows = c.execute("SELECT paper_id, filename, title, authors, year, page_count, uploaded_at "
                         "FROM papers ORDER BY uploaded_at DESC LIMIT 100").fetchall()
    return {"papers": [{**dict(r), "authors": json.loads(r["authors"] or "[]")} for r in rows]}


@app.get("/api/graph")
def graph_overview():
    with db() as c:
        count = lambda t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        return {"papers": count("papers"), "chunks": count("chunks"),
                "entities": count("entities"), "relations": count("edges")}