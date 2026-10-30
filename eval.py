#!/usr/bin/env python3
"""
RAG eval runner (fixed version).

Usage:
    uv add httpx anthropic python-dotenv
    $env:ANTHROPIC_API_KEY="sk-ant-..."     # needed only for the LLM judge (or put it in .env)
    uv run python eval.py --questions eval_questions.json --out eval_results.json

questions.json format (list of objects):
[
  {
    "id": "q01",
    "type": "specific",                # specific | multi | unanswerable
    "question": "What limitations are mentioned in the short text topic modeling survey?",
    "expected_papers": ["Short Text Topic Modeling Techniques, Applications, and Performance: A Survey"],
    "keywords": ["sparsity", "co-occurrence", "external knowledge"],
    "reference": "optional reference answer for the judge",
    "require_citation": true           # optional, default true (set false for aggregate questions)
  },
  {
    "id": "q09",
    "type": "unanswerable",
    "question": "What does the survey say about the best topic model for Arabic short texts?"
  }
]

The API response is expected to look like:
{"answer": str, "sources": [{"paper_title": str, "filename": str, "chunk_index": int, "score": float}, ...]}
expected_papers must match the API's paper_title (comparison is case/punctuation-insensitive).
"""

import argparse
import json
import os
import re
import statistics
import time

import httpx

try:  # optional: load ANTHROPIC_API_KEY etc. from .env
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Name of the request field your /api/chat expects. Override with --payload-key.
PAYLOAD_KEY = "question"
EXTRA_PAYLOAD = {}  # e.g. {"top_k": 5}; override with --extra-payload '{"top_k": 5}'

# --------------------------------------------------------------------------
# Detectors
# --------------------------------------------------------------------------

CITATION_RE = re.compile(
    "|".join(
        [
            r"\[[^\]]*chunk\s*\d+[^\]]*\]",       # [Paper, chunk 3] / [chunk 7]
            r"\[Source:[^\]]+\]",                  # [Source: ...]
            r"【[^】]*chunk\s*\d+[^】]*】",          # 【...chunk 14】
        ]
    ),
    re.IGNORECASE,
)


def has_citation(answer: str) -> bool:
    return bool(CITATION_RE.search(answer or ""))


REFUSAL_RE = re.compile(
    r"^\W*(?:"
    r"i (?:could not|couldn't|can't|cannot|was unable to) find"
    r"|there is no (?:information|mention|evidence)"
    r"|the (?:provided |retrieved )?(?:context|excerpts?|documents?|sources?|library|papers?|survey)"
    r"(?:\s+\w+){0,4}\s+(?:do(?:es)? not|don't|doesn't) "
    r"(?:contain|mention|include|provide|discuss|cover|recommend|address)"
    r"|no (?:relevant|mention|information|paper|papers|document|documents|source|sources)"
    r"|not (?:mentioned|covered|found) in"
    r"|i don't have (?:enough )?information"
    r"|none of the (?:papers|documents|sources)"
    r")",
    re.IGNORECASE,
)


def _clean_for_refusal(answer: str) -> str:
    answer = re.sub(r"[*#>_`]", "", answer or "").strip()
    answer = re.sub(r"^\s*answer\s*[:\-]?\s*", "", answer, flags=re.IGNORECASE)
    return answer.strip()


def is_refusal(answer: str) -> bool:
    answer = _clean_for_refusal(answer)
    head = answer[:300]
    if REFUSAL_RE.search(head):
        return True
    # short answer with no citation that contains a negation -> likely a refusal
    return (
        len(answer.split()) < 60
        and not has_citation(answer)
        and re.search(r"\b(not|no)\b", head.lower()) is not None
    )


# --------------------------------------------------------------------------
# Retrieval metrics
# --------------------------------------------------------------------------

SOURCE_RE = re.compile(r"^(?P<paper>.*?)\s*\(chunk\s*(?P<chunk>\d+)\)\s*$", re.IGNORECASE)


def source_paper(src: str) -> str:
    m = SOURCE_RE.match(src.strip())
    return (m.group("paper") if m else src).strip()


def norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def title_key(s: str) -> str:
    """Letters/digits only, lowercased: ignores spaces, hyphens, punctuation (PDF-extraction glitches)."""
    return re.sub(r"[\W_]+", "", s.lower())


def titles_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    from difflib import SequenceMatcher

    return SequenceMatcher(None, a, b).ratio() >= 0.9


def retrieval_metrics(sources, expected_papers):
    """hit, precision, coverage, mrr. Returns None for questions with no expected papers."""
    if not expected_papers:
        return None
    expected = [title_key(p) for p in expected_papers]
    papers = [title_key(source_paper(s)) for s in sources]
    relevant = [any(titles_match(p, e) for e in expected) for p in papers]

    hit = any(relevant)
    precision = sum(relevant) / len(papers) if papers else 0.0
    covered = sum(any(titles_match(p, e) for p in papers) for e in expected)
    coverage = covered / len(expected)
    mrr = 0.0
    for i, r in enumerate(relevant, start=1):
        if r:
            mrr = 1.0 / i
            break
    return {
        "hit": hit,
        "precision": round(precision, 3),
        "coverage": round(coverage, 3),
        "mrr": round(mrr, 3),
    }


def keyword_recall(answer: str, keywords):
    if not keywords:
        return None
    def clean(s):
        # The model often writes non-breaking hyphens (U+2011) that never match a plain "-".
        return re.sub(r"[\u2010-\u2015\u2212]", "-", s).lower()

    a = clean(answer)
    found = [k for k in keywords if clean(k) in a]
    return round(len(found) / len(keywords), 3), [k for k in keywords if k not in found]


# --------------------------------------------------------------------------
# API client with retry / backoff
# --------------------------------------------------------------------------


def build_payload(question: str) -> dict:
    return {PAYLOAD_KEY: question, **EXTRA_PAYLOAD}


def _format_source(s) -> str:
    """Normalize a source to 'Paper title (chunk N)'. Accepts strings or dicts."""
    if isinstance(s, str):
        return s
    if isinstance(s, dict):
        title = (
            s.get("paper_title")
            or s.get("title")
            or s.get("paper")
            or s.get("source")
            or s.get("document")
            or s.get("filename")
            or "unknown"
        )
        chunk = s.get("chunk_index")
        if chunk is None:
            chunk = s.get("chunk", s.get("chunk_id"))
        return f"{title} (chunk {chunk})" if chunk is not None else str(title)
    return str(s)


def parse_response(data: dict):
    answer = data.get("answer") or data.get("response") or data.get("text") or ""
    sources = data.get("sources") or data.get("citations") or []
    return answer, [_format_source(s) for s in sources]


def call_chat(client: httpx.Client, url: str, question: str, retries: int, backoff: float):
    """Returns (data, latency_s, error). error is None on success.
    Distinguishes timeout / http_5xx / connection errors."""
    last_err = None
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            r = client.post(url, json=build_payload(question))
            latency = time.time() - t0
            body_l = r.text.lower()
            too_large = "413" in r.text or "request too large" in body_l
            if r.status_code >= 500 and (too_large or "429" in r.text or "rate limit" in body_l):
                # Provider quota exhausted (429) or prompt bigger than the per-minute limit (413):
                # retrying will not help, so report it once.
                return None, latency, {
                    "kind": "request_too_large" if too_large else "rate_limit",
                    "status": r.status_code,
                    "body": r.text[:500],
                    "latency_s": round(latency, 2),
                }
            if r.status_code >= 500:
                last_err = {
                    "kind": "http_5xx",
                    "status": r.status_code,
                    "body": r.text[:500],
                    "latency_s": round(latency, 2),
                }
            else:
                r.raise_for_status()
                return r.json(), latency, None
        except httpx.TimeoutException:
            last_err = {"kind": "timeout", "latency_s": round(time.time() - t0, 2)}
        except httpx.HTTPStatusError as e:
            return None, time.time() - t0, {
                "kind": "http_4xx",
                "status": e.response.status_code,
                "body": e.response.text[:500],
            }
        except httpx.HTTPError as e:
            last_err = {"kind": "connection", "detail": str(e)[:200]}
        if attempt < retries:
            time.sleep(backoff * (2 ** attempt))
    last_err["attempts"] = retries + 1
    return None, last_err.get("latency_s", 0.0), last_err


# --------------------------------------------------------------------------
# LLM judge (runs on EVERY question)
# --------------------------------------------------------------------------

ANSWERABLE_JUDGE_PROMPT = """You are grading a RAG system's answer about a library of research papers.

Question: {question}
Reference answer / key points (may be empty): {reference}
System answer: {answer}
Sources returned: {sources}

Score 1-5:
5 = Fully correct, complete, consistent with the reference; no fabricated specifics.
4 = Mostly correct; minor omissions or slightly imprecise details.
3 = Partially correct; notable gaps or some doubtful claims.
2 = Mostly wrong, off-topic, or built on irrelevant sources.
1 = Wrong or fabricated.

Be skeptical of specific numbers, metrics, dataset names that look unsupported.
Return ONLY JSON: {{"score": int, "suspicious_claims": [str], "reason": str}}"""

UNANSWERABLE_JUDGE_PROMPT = """You are grading a RAG system on a question that CANNOT be answered from the library.

Question: {question}
System answer: {answer}
Sources returned: {sources}

Score 1-5:
5 = Clearly states the library doesn't contain this information; no fabricated claims;
    optionally mentions what the papers DO cover.
4 = Declines correctly but with minor unnecessary hedging or tangential info.
3 = Declines but also presents loosely related content as if it were an answer.
2 = Gives a confident answer built mostly from tangential sources.
1 = Fabricates specifics (methods, numbers, paper names) to answer.

Return ONLY JSON: {{"score": int, "suspicious_claims": [str], "reason": str}}"""


def judge(anthropic_client, model: str, q: dict, answer: str, sources):
    tmpl = UNANSWERABLE_JUDGE_PROMPT if q["type"] == "unanswerable" else ANSWERABLE_JUDGE_PROMPT
    prompt = tmpl.format(
        question=q["question"],
        reference=q.get("reference", ""),
        answer=answer,
        sources=json.dumps(sources, ensure_ascii=False),
    )
    try:
        msg = anthropic_client.messages.create(
            model=model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        text = re.sub(r"```json|```", "", text).strip()
        j = json.loads(text)
        return int(j["score"]), j.get("reason", ""), j.get("suspicious_claims", [])
    except Exception as e:  # judge failure must not kill the run
        return None, f"judge_error: {e}", []


# --------------------------------------------------------------------------
# Per-question evaluation
# --------------------------------------------------------------------------


def evaluate_question(q, client, args, anthropic_client):
    rec = {"id": q["id"], "type": q["type"], "question": q["question"]}

    data, latency, err = call_chat(client, args.api_url, q["question"], args.retries, args.backoff)
    rec["latency_s"] = round(latency, 2)
    if err:
        rec["error"] = err
        rec["passed"] = False
        return rec

    answer, sources = parse_response(data)
    rec.update(
        answer=answer,
        sources=sources,
        n_sources=len(sources),
        has_citation=has_citation(answer),
        refused=is_refusal(answer),
    )

    rm = retrieval_metrics(sources, q.get("expected_papers", []))
    if rm:
        rec.update(rm)
    kr = keyword_recall(answer, q.get("keywords", []))
    if kr:
        rec["keyword_recall"], rec["missing_keywords"] = kr

    if anthropic_client:
        score, reason, suspicious = judge(anthropic_client, args.judge_model, q, answer, sources)
        rec["judge"], rec["judge_reason"], rec["suspicious_claims"] = score, reason, suspicious
    else:
        rec["judge"] = None

    # ---- pass/fail ----
    j = rec["judge"]
    reasons = []
    if q["type"] == "unanswerable":
        if not rec["refused"]:
            reasons.append("did not refuse")
        if j is not None and j < 4:
            reasons.append(f"judge score {j} < 4")
    else:
        if rec["refused"]:
            reasons.append("answer is a refusal")
        if q.get("require_citation", True) and not rec["has_citation"]:
            reasons.append("no citation")
        if "hit" in rec and not rec["hit"]:
            reasons.append("no expected paper retrieved")
        if "keyword_recall" in rec and rec["keyword_recall"] < args.min_keyword_recall:
            reasons.append(f"keyword recall {rec['keyword_recall']} < {args.min_keyword_recall}")
        if j is not None and j < 4:
            reasons.append(f"judge score {j} < 4")
    rec["fail_reasons"] = reasons
    rec["passed"] = not reasons
    return rec


# --------------------------------------------------------------------------
# Summary (averages over questions that actually ran; n always shown)
# --------------------------------------------------------------------------


def mean(vals):
    vals = [v for v in vals if v is not None]
    return (round(statistics.mean(vals), 3), len(vals)) if vals else (None, 0)


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "n/a"


def summarize(results):
    total = len(results)
    ran = [r for r in results if "error" not in r]
    errored = [r for r in results if "error" in r]

    print("\n===== SUMMARY =====")
    print(f"Questions: {total}   ran: {len(ran)}   errored: {len(errored)}")
    for r in errored:
        e = r["error"]
        print(f"  ERROR {r['id']} ({r['type']}): {e['kind']} {e.get('status', '')} after {e.get('attempts', 1)} attempt(s)")
        if e.get("body"):
            print(f"        body: {e['body'][:300]}")

    n_pass = sum(r["passed"] for r in results)
    print(f"\nPass rate (errors count as FAIL): {n_pass}/{total}  ({pct(n_pass, total)})")
    for t in ["specific", "multi", "unanswerable"]:
        rs = [r for r in results if r["type"] == t]
        if rs:
            p = sum(r["passed"] for r in rs)
            print(f"  {t:13s} pass {p}/{len(rs)}  ({pct(p, len(rs))})   (ran {sum('error' not in r for r in rs)}/{len(rs)})")

    print("\nRetrieval metrics (answerable only):")
    for k in ["precision", "coverage", "mrr"]:
        m, n = mean([r.get(k) for r in ran])
        print(f"  {k:10s} {m}  (n={n})")
    hits = [r["hit"] for r in ran if "hit" in r]
    if hits:
        print(f"  hit-rate   {sum(hits)/len(hits):.3f}  ({pct(sum(hits), len(hits))}, n={len(hits)})")

    m, n = mean([r.get("keyword_recall") for r in ran])
    print(f"Keyword recall: {m}  (n={n})")
    ans = [r for r in ran if r["type"] != "unanswerable"]
    if ans:
        c = sum(r["has_citation"] for r in ans)
        print(f"Citation rate (answerable): {c}/{len(ans)}  ({pct(c, len(ans))})")
    un = [r for r in ran if r["type"] == "unanswerable"]
    if un:
        c = sum(r["refused"] for r in un)
        print(f"Correct refusals (unanswerable): {c}/{len(un)}  ({pct(c, len(un))})")
    m, n = mean([r.get("judge") for r in ran])
    print(f"Judge score (1-5): {m}  (n={n} of {len(ran)} ran)")

    lats = [r["latency_s"] for r in ran]
    if lats:
        print(f"Latency  avg={statistics.mean(lats):.1f}s  p50={statistics.median(lats):.1f}s  max={max(lats):.1f}s  (n={len(lats)})")

    flagged = [r for r in ran if r.get("suspicious_claims")]
    if flagged:
        print("\nQuestions with suspicious claims flagged by judge:")
        for r in flagged:
            print(f"  {r['id']}: {r['suspicious_claims'][:3]}")

    failed = [r for r in results if not r["passed"]]
    if failed:
        print("\nFailed questions and why:")
        for r in failed:
            why = r.get("fail_reasons") or ([f"error: {r['error']['kind']}"] if "error" in r else ["unknown"])
            print(f"  {r['id']} ({r['type']}): {', '.join(why)}")

    # ---- overall percentages ----
    ran_pass = sum(r["passed"] for r in ran)
    print("\n===== OVERALL EVALUATION =====")
    print(f"Overall pass rate (all questions):  {pct(n_pass, total)}  ({n_pass}/{total})")
    print(f"Pass rate (questions that ran):     {pct(ran_pass, len(ran))}  ({ran_pass}/{len(ran)})")
    if hits:
        print(f"Retrieval hit-rate:                 {pct(sum(hits), len(hits))}")
    if ans:
        print(f"Citation rate:                      {pct(sum(r['has_citation'] for r in ans), len(ans))}")
    if un:
        print(f"Correct refusals:                   {pct(sum(r['refused'] for r in un), len(un))}")
    jm, jn = mean([r.get("judge") for r in ran])
    if jm is not None:
        print(f"Judge score:                        {pct(jm, 5)}  (avg {jm}/5, n={jn})")
    else:
        print("Judge score:                        n/a (judge did not run)")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main():
    global PAYLOAD_KEY, EXTRA_PAYLOAD
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-url", default="http://localhost:8000/api/chat")
    ap.add_argument("--questions", default="eval_questions.json")
    ap.add_argument("--out", default="eval_results.json")
    ap.add_argument("--payload-key", default=PAYLOAD_KEY, help="request field name, e.g. question / query / message")
    ap.add_argument("--extra-payload", default="{}", help='extra JSON fields, e.g. \'{"top_k": 5}\'')
    ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--backoff", type=float, default=2.0)
    ap.add_argument("--judge-model", default="claude-sonnet-5-5")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--only", default="", help="comma-separated question ids to run, e.g. q08,q09,q10 "
                    "(results are merged into the existing --out file)")
    ap.add_argument("--delay", type=float, default=0.0, help="seconds to wait between questions (helps with rate limits)")
    ap.add_argument("--min-keyword-recall", type=float, default=0.5)
    args = ap.parse_args()

    PAYLOAD_KEY = args.payload_key
    EXTRA_PAYLOAD = json.loads(args.extra_payload)

    with open(args.questions, encoding="utf-8") as f:
        questions = json.load(f)

    anthropic_client = None
    if not args.no_judge:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("[warn] ANTHROPIC_API_KEY is not set -> judge disabled. "
                  "Set it (or use .env) or pass --no-judge to silence this.")
        else:
            try:
                import anthropic
                anthropic_client = anthropic.Anthropic()
            except Exception as e:
                print(f"[warn] judge disabled: {e}")

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    to_run = [q for q in questions if not only or q["id"] in only]

    new_results = []
    with httpx.Client(timeout=args.timeout) as client:
        for i, q in enumerate(to_run):
            print(f"-> {q['id']} ({q['type']}) {q['question'][:70]}")
            rec = evaluate_question(q, client, args, anthropic_client)
            status = "ERROR" if "error" in rec else ("PASS" if rec["passed"] else "FAIL")
            print(f"   {status}  {rec['latency_s']}s")
            new_results.append(rec)
            if args.delay and i < len(to_run) - 1:
                time.sleep(args.delay)

    results = new_results
    if only and os.path.exists(args.out):
        # Merge re-run questions into the previous results, keeping the question-file order.
        try:
            with open(args.out, encoding="utf-8") as f:
                old = {r["id"]: r for r in json.load(f)}
        except Exception:
            old = {}
        old.update({r["id"]: r for r in new_results})
        results = [old[q["id"]] for q in questions if q["id"] in old]

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    summarize(results)
    print(f"\nFull results written to {args.out}")


if __name__ == "__main__":
    main()