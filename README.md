# HDU RAG Chatbot

A chatbot that answers questions about the fictional **Horizon Delta University (HDU)** using its documents: course catalog, student handbook, tuition and scholarships, FAQ, and an Arabic student services guide.

It is an **agentic RAG** system. Instead of searching once, the LLM decides when to search, writes its own search queries, and can search several times before it answers. The chat page shows every step the agent took and the document chunks it used.

> HDU is fictional. All names, prices and dates in the documents are invented for testing.

## Requirements

- Python 3.11 (see `.python-version`)
- [uv](https://docs.astral.sh/uv/) (recommended), or plain `pip`
- An [OpenRouter](https://openrouter.ai/keys) API key with some credits

## Quick start (with uv)

```bash
# 1. install the dependencies (creates .venv automatically)
uv sync

# 2. add your API key
cp .env.example .env        # on Windows PowerShell: copy .env.example .env
# open .env and put your key after OPENROUTER_API_KEY=

# 3. put your documents (PDF, TXT, MD) in the data/ folder

# 4. build the vector database
uv run python task.py

# 5. start the chatbot
uv run python app.py
```

Open http://127.0.0.1:5000 in your browser.

Run `uv run python task.py` again whenever you add or change a document, then restart `app.py`.

Install uv with `pip install uv` if you do not have it.

## Without uv (pip)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows. On Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # then add your key
python task.py
python app.py
```

## Configuration

All settings are read from environment variables or the `.env` file (see `config.py`). Nothing secret is stored in the code, and `.env` is ignored by git. Only `OPENROUTER_API_KEY` is required.

| Variable | Default | Meaning |
|---|---|---|
| `OPENROUTER_API_KEY` | (required) | Your OpenRouter key |
| `CHAT_MODEL` | `openai/gpt-4o-mini` | The LLM. It must support tool calling |
| `EMBED_MODEL` | `baai/bge-m3` | Embedding model. Changing it needs a new run of `task.py` |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | API address |
| `DATA_DIR` | `data` | Folder with the documents |
| `DB_DIR` | `chroma_db` | Where the vector database is saved |
| `OUTPUT_DIR` | `output` | Where `chunks.json` is saved |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1500` / `300` | Chunk length and overlap, in characters |
| `TOP_K` | `4` | Chunks returned by each search |
| `MAX_STEPS` | `6` | Maximum tool rounds before the agent must answer |
| `MAX_TOKENS` | `600` | Maximum length of each LLM reply |
| `SKIP_FILES_CONTAINING` | `SUPERSEDED` | Files with this word in the name are hidden from the agent. Empty = hide nothing |
| `HOST` / `PORT` | `127.0.0.1` / `5000` | Web server address |
| `FLASK_DEBUG` | `false` | Set to `true` for auto-reload while developing |

## Project structure

```
session2task2/
├── app.py              # web server + the agent loop
├── task.py             # builds the vector database
├── config.py           # all settings, read from the environment
├── embeddings.py       # OpenRouter client and embeddings (used by both scripts)
├── templates/          # index.html
├── static/             # style.css, script.js
├── data/               # your documents
├── docs/               # test questions
├── tests/              # tests that need no network or API key
├── pyproject.toml      # dependencies (uv)
├── uv.lock             # exact versions
├── requirements.txt    # same dependencies for pip users
└── .env.example        # template for your settings
```

Generated at runtime and not committed: `chroma_db/` (the vector database) and `output/chunks.json` (every chunk and its overlap, handy for debugging).

## How it works

```
documents --> task.py --> chunks --> embeddings --> Chroma database
                                                        |
question --> agent (LLM) <---- search_documents tool ---+
                v
        answer + steps + sources  -->  chat page
```

1. **Ingest (`task.py`):** files are read, split into overlapping chunks, embedded, and stored in Chroma.
2. **Agent loop (`app.py`):** the LLM reads the question and calls `search_documents` with a query it writes itself. It reads the result and decides whether to search again. After at most `MAX_STEPS` rounds it writes the answer.
3. **Chat page:** shows the answer, an "Agent steps" list, and a "Sources" list.

## Tests

```bash
uv run pytest
```

The tests need no internet and no API key. They use a fake LLM and cover the web endpoints, the agent loop (search, step limit, unknown tool) and chunk overlap detection.

## Example questions

More are in `docs/university_test_questions.md`.

| Question | Expected answer |
|---|---|
| Who teaches CAI-301? | Dr. Karim Nabil |
| What are the prerequisites for CAI-201? | CAI-101 |
| A Business student takes 18 credit hours with installments. What is due on 10 September? | 35,272 EGP |
| Entry Excellence 50% + Sibling 10% + Need-Based 30%. Total discount? | 60% (the cap) |
| كم سعر الغرفة المزدوجة في السكن الجامعي؟ | 11,000 جنيه للفرد في الفصل |
| Is there a cafeteria on campus? | It should say it could not find it |

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `OPENROUTER_API_KEY is missing` | Copy `.env.example` to `.env` and add your key. Restart after editing `.env` |
| `401 - User not found` | The key is wrong or deleted. Create a new one at openrouter.ai/keys |
| `402 - requires more credits` | Add credits at openrouter.ai/settings/credits, or use a cheaper `CHAT_MODEL` |
| `Vector database not found` | Run `uv run python task.py` first |
| Answer says "not found" for something that is in a document | Open `output/chunks.json` and search for it. If it is missing, the file is not in `data/`. Add it, run `task.py`, restart `app.py` |
| Chatbot keeps showing old data after `task.py` | Restart `app.py`. It opens the database at the first question |
| `Cannot delete chroma_db` when ingesting | Stop `app.py` first, it is using the database |
| Wrong answer | Open **Agent steps**: did it search for everything it needed? Then open **Sources**: is the right chunk there? If yes, try a stronger `CHAT_MODEL` |

## Known limitations

- There is no login. The server is meant to run locally (`127.0.0.1`), not on the open internet.
- The agent remembers only the last 6 messages of the chat.
- Answer quality depends on the chosen model. Small models can stop searching too early on multi-step money questions, and they can make arithmetic mistakes because the agent has no calculator tool.
- Retrieval uses vector search only (no keyword search and no reranking).