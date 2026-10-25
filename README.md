# HDU Catalog Chatbot (Agentic RAG)

A chatbot that answers questions about the fictional Horizon Delta University (HDU) using its documents: course catalog, student handbook, tuition and scholarships, FAQ, and an Arabic student services guide.

The chatbot is an **agentic RAG** system. The LLM decides when to search the documents, can search several times with different queries, and uses a calculator for math before it answers.

## How it works

```
data/ (PDF, TXT, MD)
   |
   |  task.py: read -> split into chunks -> embed (bge-m3 via OpenRouter) -> save
   v
chroma_db/ (vector database)
   |
   |  app.py: the agent loop
   |    1. LLM reads the question
   |    2. LLM calls a tool: search_documents(query) or calculate(expression)
   |    3. LLM reads the result, and searches again if something is missing
   |    4. LLM writes the final answer
   v
Chat page (templates/index.html + static/style.css + static/script.js)
   shows the answer, the "Agent steps" and the "Sources"
```

### RAG type history

| Version | Type | Description |
|---|---|---|
| 1 | Naive RAG | Search once with the question, send the top chunks to the LLM |
| 2 | Agentic RAG | The LLM plans, searches several times, and uses tools |

## Project structure

```
session2task2/
├── task.py            # builds the vector database
├── app.py             # Flask server + agent
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── script.js
├── data/              # your documents (PDF, TXT, MD)
├── chroma_db/         # created by task.py (not pushed to git)
├── output/
│   └── chunks.json    # created by task.py, shows every chunk and its overlap
├── .env               # your API key (not pushed to git)
├── .gitignore
└── README.md
```

## Setup

1. Install the packages:
   ```
   pip install langchain-community langchain-text-splitters langchain-chroma langchain-core openai flask python-dotenv pypdf
   ```
2. Create a `.env` file with your OpenRouter key (no quotes, no spaces):
   ```
   OPENROUTER_API_KEY=your_key_here
   ```
3. Put all documents inside the `data/` folder.
4. Build the database:
   ```
   python task.py
   ```
5. Start the chatbot:
   ```
   python app.py
   ```
6. Open http://127.0.0.1:5000

Run `task.py` again every time you add or change a document, then restart `app.py`.

## Settings

| Setting | File | Meaning |
|---|---|---|
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | task.py | Size of each chunk and how much neighbouring chunks share |
| `EMBED_MODEL` | task.py, app.py | Must be the same in both files |
| `CHAT_MODEL` | app.py | The LLM. It must support tool calling |
| `TOP_K` | app.py | Chunks returned by each search |
| `MAX_STEPS` | app.py | Maximum tool rounds before the agent must answer |
| `MAX_TOKENS` | app.py | Maximum reply length (keeps cost low) |
| `SKIP_FILES_CONTAINING` | app.py | Files with this word in the name are hidden from the agent |

---

## Problems we found and how we handled them

### 1. Embedding crash: `unexpected keyword argument 'check_embedding_ctx_length'`
- **Problem:** `task.py` stopped at the embedding step with a `TypeError`. The installed `langchain-openai` version passed an option to the OpenAI client that it does not accept.
- **Fix:** Replaced `OpenAIEmbeddings` with a small `OpenRouterEmbeddings` class that calls OpenRouter directly. Upgrading with `pip install -U langchain-openai openai` also works.
- **Status:** Fixed

### 2. `401 - User not found`
- **Problem:** OpenRouter did not accept the API key.
- **Fix:** Created a fresh key, checked that `.env` has one clean line, and used `load_dotenv(override=True)` so an old key saved in Windows does not win over the `.env` file. Restart the script after changing `.env`.
- **Status:** Fixed

### 3. Page showed "Could not reach the server" for every error
- **Problem:** The search step was outside the `try` block in `app.py`. When it failed, Flask returned an HTML error page and the JavaScript showed a generic message.
- **Fix:** Moved the whole request inside `try/except`, so the real error now appears in the chat bubble.
- **Status:** Fixed

### 4. PowerShell `ParserError` when adding code
- **Problem:** `load_dotenv(override=True)` was typed into the terminal instead of the `.py` file.
- **Fix:** Python code goes into the file in the editor. The terminal only runs commands like `python app.py`.
- **Status:** Fixed

### 5. Arabic question answered "not found"
- **Problem:** `HDU_Student_Services_AR.md` was not in `data/`, so it was never ingested. The bot correctly said it could not find the answer.
- **Fix:** Copied the file into `data/` and ran `task.py` again. Checked `output/chunks.json` to confirm the chunks appeared, then restarted `app.py`.
- **Status:** Fixed. The double room price (11,000 per person per semester) is now answered in Arabic.
- **Lesson:** When an answer is "not found", first check `chunks.json`, then the Sources list.

### 6. Make-up exam fee looked like a hallucination
- **Problem:** The bot answered 300 EGP and we assumed it was invented.
- **Fix:** None needed. `HDU_Student_FAQ.txt` was in `data/` and contains that fee, so the answer was correct. The same number (300) also appears as the late payment fee in the old 2025-26 policy, which is why it looked suspicious.
- **Lesson:** Verify against `chunks.json` before calling an answer wrong.
- **Status:** Not a bug

### 7. The old 2025-26 policy competes with the new one
- **Problem:** The superseded tuition file is in the database, so searches can return old numbers (3,800 instead of 4,200 per credit hour, and so on).
- **Fix:** Two layers: a prompt rule to use 2026-2027 documents only, and a code filter (`SKIP_FILES_CONTAINING = "SUPERSEDED"`) that removes those chunks from search results. Set it to something else to test the trap again.
- **Status:** Fixed

### 8. Wrong arithmetic
- **Problem:** The LLM calculated 58,800 minus 25% as 43,350 instead of 44,100, so the total was 45,250 instead of 46,000.
- **Fix:** Added a `calculate` tool (a safe expression evaluator) and a prompt rule that every calculation must use it. Also set `temperature=0`.
- **Status:** Fixed

### 9. `402 - requires more credits, or fewer max_tokens`
- **Problem:** No reply length was set, so each request asked for up to 16,384 tokens. With `gpt-4o`, the account balance could not cover that.
- **Fix:** Added `max_tokens=600`, and use `gpt-4o-mini` as the default model. Adding credits at openrouter.ai/settings/credits also solves it.
- **Status:** Fixed

### 10. Installment question ignored the installment plan
- **Problem:** "A Business student takes 18 credit hours with installments. What is due on 10 September?" returned 66,700 EGP (full tuition plus fees). The correct answer is **35,272 EGP**: (64,800 x 1.03) / 2 + 1,900 fees.
- **Fix applied:** Moved from naive RAG to agentic RAG, so the model can search for tuition, the installment rules and the fees separately. The system prompt now requires it to search for the rules of every plan, discount or refund in the question.
- **Status:** Fix applied, needs re-testing

### 11. Discount cap ignored
- **Problem:** "Entry Excellence 50% + Sibling 10% + Need-Based 30%" returned 90%. The documents say the total discount can never exceed **60%**.
- **Cause:** The agent searched once and stopped. Also, the scholarship table and its rules were split into two chunks, so the cap was not retrieved with the table.
- **Fix applied:** The prompt now forces a search for limits and caps on money questions. In `task.py`, `CHUNK_SIZE = 1500` and `CHUNK_OVERLAP = 300` keep a table together with its rules. `MAX_STEPS = 6` gives the agent room for extra searches.
- **Status:** Fix applied, needs re-testing

### 12. Raw `**bold**` markdown in answers
- **Problem:** The chat bubble shows plain text, so the model's markdown appeared as asterisks.
- **Fix:** Added a prompt rule: do not use markdown formatting.
- **Status:** Fixed

### 13. API key and database must not be pushed to GitHub
- **Problem:** `.env` contains the secret key, and `chroma_db/` is generated data.
- **Fix:** Added a `.gitignore` with `.env`, `chroma_db/` and Python cache files. Always check `git status` before committing. If a key was ever committed, create a new key and delete the old one.
- **Status:** Fixed

---

## Test questions

| Question | Expected answer |
|---|---|
| Who teaches CAI-301? | Dr. Karim Nabil |
| What are the prerequisites for CAI-201? | CAI-101 |
| What is the tuition per credit hour for Computing and AI? | 4,200 EGP (not 3,800) |
| A CAI student takes 14 credit hours and has the Merit Scholarship. What do they pay? | 46,000 EGP |
| A Business student takes 18 credit hours with installments. What is due on 10 September? | 35,272 EGP |
| Entry Excellence 50% + Sibling 10% + Need-Based 30%. Total discount? | 60% (the cap) |
| I'm on academic probation. What changes? | 12 credit hour maximum, advisor meeting each semester, Entry Excellence and Merit scholarships suspended |
| What is the make-up exam fee? | 300 EGP (waived with hospital documentation) |
| كم سعر الغرفة المزدوجة في السكن الجامعي؟ | 11,000 جنيه للفرد في الفصل |
| How much is the transport subscription? | 2,500 EGP per semester |
| Is there a cafeteria on campus? | Should say it could not find it |

## How to debug a wrong answer

1. Open **Agent steps** under the answer. Did the agent search for everything it needed, with good queries?
2. Open **Sources**. Is the right chunk there?
3. Open `output/chunks.json`. Is the information in the database at all, and is it in one piece?
4. If the right chunk was found but the answer is still wrong, the model is the problem. Try a stronger `CHAT_MODEL`.

## Possible next steps

- Hybrid search (keywords plus vectors) for exact terms such as course codes
- A reranker to put the best chunks first
- Metadata filtering by document type or year
- Streaming answers into the chat page
