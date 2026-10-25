# Reranking for the GlowDerma RAG chatbot

This task adds a **reranking step** to the retrieval part of the chatbot and documents a retrieval problem found while testing (a product price that the bot failed to answer) together with the fix.

> GlowDerma Skincare is a fictional company. The PDF is a test document, and nothing here is medical advice.

## What changed

Only two files were modified:

| File | Purpose |
|---|---|
| `src/ai_sts/task5.py` | Terminal chatbot, now with reranking |
| `src/ai_sts/app.py` | Web page backend, now with reranking |

### Retrieval flow

```
question
   |
   v
vector search in Chroma  ->  top FETCH_K chunks (20)
   |
   v
reranker (cohere/rerank-v3.5 via OpenRouter)  ->  best TOP_K chunks (6)
   |
   v
chat model (openai/gpt-4o-mini)  ->  answer + source pages
```

Vector search is fast but only roughly ordered. The reranker reads the question together with each candidate chunk and scores how well that chunk answers it, so the chunks sent to the chat model are better chosen.

### Settings (top of `task5.py` and `app.py`)

| Setting | Value | Meaning |
|---|---|---|
| `FETCH_K` | `20` | Candidates taken from the vector search |
| `TOP_K` | `6` | Chunks kept after reranking and sent to the chat model |
| `RERANK_BACKEND` | `"openrouter"` | Use the OpenRouter rerank API. `"local"` uses FlashRank on your PC instead (needs `python -m pip install flashrank`) |
| `RERANK_MODEL` | `cohere/rerank-v3.5` | Reranker used with the OpenRouter backend |
| `CHAT_MODEL` | `openai/gpt-4o-mini` | Model that writes the answer |

If the rerank call fails for any reason, the code prints `(rerank failed, using vector-search order: ...)` and continues with the plain vector-search order, so the chat keeps working.

## Problem found during testing: price question not answered

**Question:** `What is the price of GD-SE-303?`

**Bot answer:** `I don't have that information.`
**Sources shown:** pages 4 and 8.
**Expected:** 450 EGP, stated on page 4 (Vitamin C Brightening Serum).

### Why it happened

The retrieval returned page 4, but the chunks sent to the model did not contain the line that gives the price. The model is instructed to answer only from the context it receives, so it correctly refused instead of guessing. This was a retrieval problem, not a hallucination problem.

The likely causes:

- With `TOP_K = 4`, only four chunks reached the model, which left little room when the product description, the price line and the comparison table sit in different chunks.
- Embeddings are weaker at matching exact codes such as `GD-SE-303` than at matching meaning, so the chunk with the price line was not always ranked in the top four.

How to check this on your own run: open the web page, click **Show the passages used** under the answer, and see whether any passage contains `price 450 EGP`. You can also search `data/chunks_report.txt` for `GD-SE-303, 30 ml` to see which chunk holds that line.

### Fix applied

Retrieve more candidates, rerank them, and give the model more of the best ones:

```python
FETCH_K = 20   # was 15
TOP_K = 6      # was 4
```

**Result:** after this change the question is answered correctly (450 EGP).

### Trade-off

A bit more cost per question: the reranker scores 20 chunks instead of 15, and the chat model receives 6 chunks instead of 4, so more tokens are sent. For a document of this size the increase is small.

### If a similar problem appears again

These options were considered but are **not** part of this task's code:

1. **Exact product-ID lookup.** When the question contains an ID like `GD-SE-303`, also fetch the chunks that contain that ID literally, then let the reranker choose among them.
2. **Larger chunks.** Raise `CHUNK_SIZE` (for example to 1200) in `task3.py` and `task4.py`, then run `task3.py` again to rebuild `chroma_db`, so a product's details stay in one chunk.
3. **Hybrid search.** Combine vector search with keyword search (BM25).

## How to run

Run everything from the project root (`AI sts`) with the virtual environment active (`(ai-sts)` shown in the prompt).

```powershell
python src\ai_sts\task5.py      # terminal chat
python src\ai_sts\app.py        # web page at http://127.0.0.1:5000
```

`chroma_db` must already exist. If it does not, run `python src\ai_sts\task3.py` first. After editing `app.py`, restart the server and refresh the page with `Ctrl+F5`.

## Test questions

| Question | Expected answer |
|---|---|
| What is the price of GD-SE-303? | 450 EGP |
| How much is GD-SU-402? | 360 EGP |
| What is the price of GD-MO-204? | 520 EGP |
| What size is GD-SE-304? | 30 ml |
| Which products contain niacinamide? | GD-SE-301 (5%) and GD-MO-202 (2%) |
| Which products contain ceramides? | GD-CL-101, GD-MO-201, GD-MO-204, GD-SU-403 |
| Can I return an opened serum because it didn't suit me? | No, unless damaged, defective or the wrong item |
| What is the full ingredient list of GD-SE-301? | Not in the document, so the bot should say it doesn't know |

For each answer, also check that the pages in `Sources` match the pages where the information appears in the PDF.
