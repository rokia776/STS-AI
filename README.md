# Research Papers GraphRAG — SQLite Edition

A local-first GraphRAG system for research papers. No database server and no cloud vector service are needed: everything is stored in one SQLite file. Embeddings can run on your own machine (free) or through an API, and the chat model can be any OpenAI-compatible endpoint.

## 1. Architecture and design choices

SQLite is a relational database, not a dedicated graph database like Neo4j. The graph is modeled with an `entities` table (nodes) and an `edges` table (paper → entity relations), and graph traversal is done with SQL joins. This is a practical graph-shaped design, but it does not offer the query ergonomics of a dedicated graph database.

Retrieval is hybrid:

1. **Vector retrieval:** the question is embedded with `BAAI/bge-m3` and compared by cosine similarity against all chunk embeddings held in memory with NumPy. Up to 10 chunks are kept, with at most 2 per paper so one paper cannot crowd out the rest.
2. **Similarity cutoff:** the best chunk always passes. Other chunks must score within `SCORE_MARGIN` of the best one and above `MIN_SCORE`. A specific question therefore returns 2 or 3 clean chunks instead of padding the context with unrelated papers.
3. **Graph expansion:** entities linked to the retrieved papers are added to the context, plus:
   - up to 3 **neighbouring papers** that share entities (methods, datasets, topics) with them, ranked by number of shared entities;
   - the **entities shared by multiple papers** across the whole library (top 20), which helps with overlap questions.
4. **LLM answer generation:** a chat model answers using only the excerpts plus graph context, writes in Markdown, and cites sources as `[Paper title, chunk N]`.

| Component | Choice | Cost |
|---|---|---|
| Database | SQLite (`graphrag.db`) | Free |
| Embeddings | `BAAI/bge-m3` (1024 dimensions), either via an API (`EMBEDDING_PROVIDER=api`, the default, through OpenRouter) or locally with `sentence-transformers` (`EMBEDDING_PROVIDER=local`) | API: per-use cost. Local: free |
| Vector search | NumPy cosine similarity in memory | Free |
| Chat / entity extraction | Any OpenAI-compatible API: OpenRouter or a local Ollama model | OpenRouter needs credits; Ollama is free |
| Evaluation judge (optional) | Anthropic API (`ANTHROPIC_API_KEY`) | Per-use cost |

### Tables

| Table | Purpose |
|---|---|
| `papers` | Paper metadata: filename, SHA-256, title, authors, year, page count |
| `chunks` | Chunk text, paper ID, chunk index, embedding vector (float32 BLOB) |
| `entities` | Canonicalized named entities: models, methods, datasets, metrics, tasks, topics |
| `edges` | Paper → entity relations: `USES_METHOD`, `USES_DATASET`, `ABOUT_TOPIC`, `USES_METRIC`, `MENTIONS` |
| `chat_messages` | Original user and assistant messages per session, with an `is_summarized` flag |
| `memory_summaries` | One running summary per session, built from older messages |

Entities are deduplicated by a lowercase canonical name. A paper–entity pair is stored once. Databases created before memory compaction existed are migrated automatically (the `is_summarized` column is added at startup).

### API response shape

`POST /api/chat` accepts `{"question": "..."}` and returns:

```json
{
  "answer": "Markdown text with [Paper title, chunk N] citations",
  "sources": [
    {
      "paper_title": "Panarchy: ripples of a boundary concept",
      "filename": "007_NLP_Panarchy_ripples_of_a_boundary_concept.pdf",
      "chunk_index": 5,
      "score": 0.7139
    }
  ]
}
```

The evaluation script depends on this shape (`paper_title` and `chunk_index` in particular).

## 2. Project layout

```text
Graph-Rag-system/
├── main.py                FastAPI app, ingestion, retrieval, chat, memory
├── ingest_data.py         Bulk-load every PDF in data/
├── index.html             Web UI (renders Markdown answers)
├── eval.py                Evaluation script
├── eval_questions.json    Evaluation question set
├── logging_config.py      Logging setup
├── pyproject.toml         Dependencies (managed with uv)
├── .env                   Your settings (never commit this)
├── data/                  Put your PDFs here
├── output/                Generated: one JSON file per paper (chunks + overlap)
├── eval_results.json      Generated: evaluation results
└── graphrag.db            Generated: the SQLite database
```

## 3. Setup with uv

Python 3.12 is recommended. PyTorch, which `sentence-transformers` needs in local mode, may not support the newest Python versions yet.

```bash
uv sync
```

If you start from a plain `requirements.txt`, use `uv add -r requirements.txt` once, then `uv sync`. Add the optional packages you need:

```bash
uv add httpx anthropic python-dotenv   # used by eval.py (anthropic = LLM judge, python-dotenv = .env loading)
uv add sentence-transformers           # only for EMBEDDING_PROVIDER=local
```

Then copy the settings template:

```bash
cp .env.example .env            # Windows PowerShell: copy .env.example .env
```

`uv run` uses the project's virtual environment automatically, so you do not need to activate it.

### Configure `.env`

```dotenv
# Chat model (entity extraction + answers)
OPENROUTER_API_KEY=your_openrouter_api_key
CHAT_MODEL=openai/gpt-4.1-mini
CHAT_MAX_TOKENS=3000
META_MAX_TOKENS=4000

# Embeddings
EMBEDDING_PROVIDER=api          # "api" (OpenRouter) or "local"
EMBEDDING_MODEL=BAAI/bge-m3

# Retrieval cutoff
SCORE_MARGIN=0.10               # how far below the best chunk a chunk may score
MIN_SCORE=0.30                  # absolute minimum similarity

# Storage
SQLITE_PATH=graphrag.db
OUTPUT_DIR=output
INCLUDE_EMBEDDINGS=0

# Evaluation judge (only needed for eval.py's LLM judge)
ANTHROPIC_API_KEY=your_anthropic_api_key
```

`MONGODB_URI`, `MONGODB_DB` and `VECTOR_INDEX_NAME` are no longer used.

| Variable | Default | Meaning |
|---|---|---|
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | Chat endpoint. Point it at Ollama for a local model |
| `LLM_API_KEY` | `OPENROUTER_API_KEY` | Key for the chat endpoint |
| `EMBEDDING_PROVIDER` | `api` | `api` sends text to OpenRouter's embeddings endpoint; `local` runs `bge-m3` on your machine |
| `CHAT_MAX_TOKENS` | `3000` | Reply limit. The request is retried with double the limit if the reply comes back empty |
| `META_MAX_TOKENS` | `4000` | Limit for entity extraction. Reasoning models need room to think |
| `SCORE_MARGIN` | `0.10` | Larger value keeps more chunks |
| `MIN_SCORE` | `0.30` | Chunks below this similarity are dropped, except the best one |
| `ANTHROPIC_API_KEY` | none | Used only by `eval.py` for the LLM judge. Without it the judge is skipped |

### Chat model options

The chat model is used for three things: extracting title and entities during ingestion, answering questions, and summarizing old conversation messages.

**Option A: OpenRouter.** Add credits at openrouter.ai/settings/credits. A few dollars is plenty. Or try a `:free` model such as `meta-llama/llama-3.3-70b-instruct:free`, but accounts without purchased credits have a small daily request limit.

**Option B: Ollama (fully free and local).** Install Ollama, run `ollama pull qwen2.5:7b`, then set:

```dotenv
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
CHAT_MODEL=qwen2.5:7b
```

For a fully free setup also set `EMBEDDING_PROVIDER=local`.

## 4. Load your papers and run

Put PDFs in `data/`, then:

```bash
uv run python ingest_data.py
uv run uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

Ingestion does this for each PDF: extract text with `pypdf`, ask the chat model for title, authors, year and entities, split the text into chunks (**1200 characters with 180 overlap**), embed the chunks, store everything in SQLite, and write a JSON file to `output/`.

- In local mode, the first run downloads `bge-m3` (about 2.2 GB, once). On CPU, embedding thousands of chunks can take 15 to 40 minutes.
- Papers are identified by SHA-256, so re-running skips files that were already loaded.
- Restart the server after running `ingest_data.py`, because the server keeps its vector index in memory. Papers uploaded through the web page are picked up immediately.
- You can also upload single PDFs from the web page.

### Chunks JSON files

Each paper gets `output/<filename>.json` showing every chunk with `start_char`, `end_char`, `overlap_with_previous`, `overlap_with_next`, the chunk text, the embedding dimension and a short embedding preview. Set `INCLUDE_EMBEDDINGS=1` to include full vectors (large files).

## 5. The web UI

- Assistant answers are rendered as Markdown (tables, bold text, lists, code). Output is sanitized with DOMPurify before it is inserted into the page. User messages stay plain text.
- The rendering libraries (`marked` and `DOMPurify`) load from a CDN. If the CDN is blocked, answers fall back to plain text.
- Under each answer, "Retrieved sources" lists the paper title and chunk index of every chunk sent to the model.
- These are prototype-level citations. Page-level citations would need chunk-to-page tracking.

## 6. Test questions

- `What limitations are mentioned in the short text topic modeling survey?`
- `Which methods or datasets appear in more than one paper?`
- `Compare the approaches used across the papers in a table.`
- `How does neural document expansion improve ad-hoc retrieval?`
- `Which paper uses reinforcement learning for image classification?` (should answer that the evidence is insufficient)

## 7. Conversation memory

Each message is stored as one record in `chat_messages`. Memory works in two layers:

- **Short-term:** every message in the session that is not yet summarized is replayed to the model in full.
- **Long-term:** once a session has 8 unsummarized messages (`COMPACT_AT`), a background task summarizes everything except the newest 2 (`KEEP_VERBATIM`) into a running summary of under 200 words, stored in `memory_summaries`. Summarized messages are marked `is_summarized=1` and are **never deleted**.

The summary is added to the system prompt, labeled as context for continuity only, not as evidence about the papers. If summarization fails, it is retried after a later message.

The session ID is per browser tab. Starting a new chat creates a new session and does not delete old records.

## 8. Evaluation

`eval.py` sends every question in `eval_questions.json` to the running server, measures retrieval and answer quality, optionally grades each answer with an LLM judge, and writes full results to `eval_results.json`.

The runner sends only the question text (`{"question": "..."}`). It does not send a session ID. If your endpoint needs extra fields (for example `top_k`), pass them with `--extra-payload`.

### Running it

```bash
uv run uvicorn main:app          # terminal 1: start the API
uv run python eval.py            # terminal 2: run the evaluation
```

The LLM judge runs by default when `ANTHROPIC_API_KEY` is set. In PowerShell, set it in the same window you run the evaluation from:

```powershell
$env:ANTHROPIC_API_KEY="sk-ant-..."
uv run python eval.py
```

You can also put the key in `.env`; the script loads it with `python-dotenv`. If the key is missing, the script prints a warning and continues without the judge (`judge` is `null`). Pass `--no-judge` to skip the judge on purpose.

| Option | Default | Meaning |
|---|---|---|
| `--api-url` | `http://localhost:8000/api/chat` | Chat endpoint |
| `--questions` | `eval_questions.json` | Question file |
| `--out` | `eval_results.json` | Output file |
| `--payload-key` | `question` | Request field name (`question`, `query`, `message`) |
| `--extra-payload` | `{}` | Extra JSON fields, for example `'{"top_k": 5}'` |
| `--timeout` | `90` | Per-request timeout in seconds |
| `--retries` / `--backoff` | `2` / `2.0` | Retries on timeouts and 5xx errors, with exponential backoff |
| `--judge-model` | `claude-sonnet-5-5` | Model used by the LLM judge |
| `--no-judge` | off | Skip the LLM judge |
| `--min-keyword-recall` | `0.5` | Minimum share of `keywords` the answer must contain |

### Question file format

```json
[
  {
    "id": "q01",
    "type": "specific",
    "question": "What limitations are mentioned in the short text topic modeling survey?",
    "expected_papers": ["Short Text Topic Modeling Techniques, Applications, and Performance: A Survey"],
    "keywords": ["sparsity", "co-occurrence", "external knowledge"],
    "reference": "Optional reference answer or key points for the judge"
  },
  {
    "id": "q08",
    "type": "multi",
    "question": "Which methods or datasets are shared by more than one paper in the library?",
    "require_citation": false
  },
  {
    "id": "q09",
    "type": "unanswerable",
    "question": "What does the survey say about the best topic model for Arabic short texts?"
  }
]
```

| Field | Required | Meaning |
|---|---|---|
| `id`, `type`, `question` | yes | `type` is `specific`, `multi` or `unanswerable` |
| `expected_papers` | no | Paper titles that should be retrieved. Retrieval metrics are computed only for questions that have it |
| `keywords` | no | Terms the answer should contain (case-insensitive substring match) |
| `reference` | no | Reference answer or key points shown to the judge |
| `require_citation` | no | Default `true`. Set `false` for aggregate or library-wide questions that do not naturally cite one paper |

Use titles that match the `paper_title` values the API returns. Run one question per paper and copy the titles from the response if unsure.

### Metrics

| Metric | Meaning |
|---|---|
| `hit` | At least one retrieved chunk comes from an expected paper |
| `precision` | Share of retrieved chunks that come from expected papers |
| `coverage` | Share of expected papers that appear in the sources |
| `mrr` | 1 divided by the rank of the first chunk from an expected paper |
| `keyword_recall` | Share of `keywords` found in the answer, plus the list of missing keywords |
| `has_citation` | The answer contains a citation such as `[Paper title, chunk N]`, `[chunk N]` or `[Source: ...]` |
| `refused` | The answer says the library does not contain the information |
| `judge` | 1-5 score from the LLM judge, plus `judge_reason` and `suspicious_claims` |
| `latency_s` | Time for the chat call |

### How titles are matched

PDF text extraction sometimes drops spaces or changes punctuation in titles (for example `NeuralRanking` instead of `Neural Ranking`). To avoid false misses, titles are compared after removing everything except letters and digits, and two titles match if they are equal, if one contains the other, or if they are at least 90% similar.

### How refusals are detected

Answers are cleaned first (Markdown symbols and a leading "Answer" label are removed), then the opening of the answer is checked for phrases such as "The excerpts from the survey do not discuss...", "No paper in the provided excerpts...", "I could not find...", or "There is no information...". Very short answers with no citation that contain a negation also count as refusals. If the system uses a different refusal wording, extend `REFUSAL_RE` in `eval.py`.

### Pass and fail rules

- **Unanswerable questions** pass when the answer is a refusal and the judge score is 4 or higher (or no judge ran).
- **Specific and multi questions** pass only if all of these hold:
  - the answer is not a refusal;
  - it contains a citation (unless `require_citation` is `false`);
  - `hit` is true, when `expected_papers` is set;
  - keyword recall meets `--min-keyword-recall`, when `keywords` is set;
  - the judge score is 4 or higher, when the judge ran.
- A request that errors out counts as a failure and is listed separately with its error type (`timeout`, `http_5xx`, `http_4xx`, `connection`).

### Reading the summary

The summary prints pass rates per question type, the retrieval metrics (with `n`, the number of questions each average covers), citation rate, correct refusals, average judge score, latency (average, median, max) and the questions where the judge flagged suspicious claims. Always read `suspicious_claims` and `judge_reason` in `eval_results.json`: they are the most direct signal of hallucinated details.

### Known findings from evaluation runs

- **Library-wide questions are weak.** For "which methods or datasets are shared by more than one paper", the answer repeated the raw "entities shared by multiple papers" list, including generic items such as `accuracy`, `dropout` and `machine learning`, with no per-paper attribution. Entity extraction is too noisy for this, and entity resolution (section 9) would help.
- **The library is larger than the evaluation set.** Sources for broad or unanswerable questions come from unrelated papers (GAN, graph neural network and distant-supervision papers). That is expected, but it means such questions should not have `expected_papers`.
- **Latency varies a lot.** Specific questions answer in 2 to 6 seconds, while multi-paper and unanswerable questions took 30 to 55 seconds in one run, probably because they use the graph and library-wide context and larger prompts.
- **Verify details that look too specific.** Some answers contained specifics (metrics, loss names, architectural components) that the judge should check against the retrieved chunks. Direct quotes in answers should also be verified against the chunk text.

To tune retrieval, change `SCORE_MARGIN` or `MIN_SCORE`, rerun the evaluation, and compare hit rate against the average number of sources per answer. Add 20 to 30 questions before trusting the numbers.

## 9. Limitations and next steps

1. **Scale:** in-memory NumPy search is fine up to tens of thousands of chunks. Beyond that, move to `sqlite-vec`, Chroma or Qdrant.
2. **Changing the embedding model:** vectors from different models cannot be mixed. Delete `graphrag.db` and re-ingest after any change to `EMBEDDING_MODEL`.
3. **Entity resolution:** merge aliases such as `Large Language Model` and `LLM`, while avoiding false merges. Filter generic terms (`accuracy`, `dropout`) that are not real methods or datasets.
4. **Relation extraction:** extract evidence-backed relations between entity pairs, not only paper → entity links.
5. **Page-level provenance:** keep page numbers per chunk and show them in citations.
6. **Answer grounding:** the model can still state something the excerpts do not say. Check key claims against the paper, and consider adding "label any inference as such" to the system prompt.
7. **Library-wide answers:** attribute shared entities to the papers that use them, and ask the model to cite them.
8. **Security:** add authentication, rate limits and strict CORS before any deployment.
9. **PDF extraction:** scanned PDFs need OCR first. `pypdf` reads embedded text only, and it can drop spaces in titles.

## 10. Troubleshooting

### Server and ingestion

- **`uvicorn` not recognized:** use `uv run uvicorn main:app --reload`.
- **numpy or pydantic_core import errors:** the environment has packages built for a different Python version. Delete `.venv` and run `uv sync` again.
- **`402 Insufficient credits` or `Payment Required`:** the OpenRouter account has no credits. Add credits, use a `:free` model, or switch to Ollama. During ingestion this means papers are stored with a filename as title and 0 entities.
- **Papers loaded with 0 entities:** the chat model failed during ingestion. Fix the chat model, delete `graphrag.db`, and re-ingest.
- **Questions return nothing or an old answer after bulk ingest:** restart the server.
- **Vector dimension errors:** you changed the embedding model without deleting `graphrag.db`.
- **Too few sources for broad questions:** raise `SCORE_MARGIN` (for example `0.15`) or lower `MIN_SCORE`.
- **Too many unrelated sources:** lower `SCORE_MARGIN` or raise `MIN_SCORE`.
- **Tables or bold text appear as raw `|` and `**`:** the Markdown libraries did not load (CDN blocked or offline). Check the browser console.
- **Empty reply from the model:** common with free "thinking" models. The server retries once with a larger token limit. If it keeps happening, increase `CHAT_MAX_TOKENS` or change `CHAT_MODEL`.
- **No PDF text:** the PDF is scanned or protected. Run OCR first.
- **Slow ingestion:** expected on CPU in local mode. Check `logs/app.log` for progress.

### Evaluation

- **Every question fails and `hit` is always false:** `expected_papers` does not match the `paper_title` values in the API's `sources`. Copy the exact titles from a real response. If every source shows as `unknown`, the source objects use a field name the script does not know; print one raw source and update `_format_source` in `eval.py`.
- **`judge` is `null` and the message says authentication could not be resolved:** `ANTHROPIC_API_KEY` is not set in the window you ran the script from. Set it (`$env:ANTHROPIC_API_KEY="..."` in PowerShell) or add it to `.env`, and make sure `anthropic` and `python-dotenv` are installed.
- **A correct refusal is marked as not refused:** the system's wording is not covered by `REFUSAL_RE`. Add the phrase to the pattern in `eval.py`.
- **`keyword_recall` is missing:** the question has no `keywords` field. Note that the field is called `keywords`, not `expected_keywords`.
- **A correct answer fails on keywords:** the answer used a synonym (for example "sparseness" instead of "sparsity"). Add synonyms, or lower `--min-keyword-recall`.
- **A library-wide question fails on citation:** set `"require_citation": false` for that question and leave out `expected_papers`.
- **Request errors:** the summary lists each error with its kind. Raise `--timeout` for slow questions, and check that the server is running at `--api-url`.

## 11. What to say about the architecture in a presentation

> "I wanted a GraphRAG system that is simple to run and mostly free. Papers, chunks, entities and relations live in a single SQLite file. Entities and papers form a graph through an edges table, and I traverse it with SQL joins to find related papers that share methods and datasets. Chunks are embedded with BAAI/bge-m3 and searched by cosine similarity, with a similarity cutoff so only relevant evidence reaches the model. The LLM answers from the retrieved excerpts plus the graph context and cites its sources. Older conversation turns are summarized into a running memory while the latest messages stay verbatim, and I measure the whole pipeline with an evaluation script covering retrieval accuracy, citations, refusal on unanswerable questions and an LLM judge that flags unsupported claims."

Be transparent that SQLite is not a dedicated graph database. If multi-hop graph reasoning becomes the main requirement, Neo4j is the more natural engine; for this project, explicit edges plus SQL joins are the graph layer.
