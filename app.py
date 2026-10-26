import json
import logging
from functools import lru_cache
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from langchain_chroma import Chroma

import config
from embeddings import OpenRouterEmbeddings, get_client

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 6  # how many old messages the bot remembers

SYSTEM_PROMPT = """You are an assistant for Horizon Delta University. You have one tool: search_documents.

1. Always search before answering a university question. Never answer from memory.
2. If the question needs several facts, search for each fact separately with a short query.
3. For money questions (tuition, fees, discounts, scholarships, installments, refunds), first search for:
   a) the tuition rate and the fees,
   b) the rules of every scholarship, discount, installment plan or refund in the question,
   c) any limit or condition that could apply, like the maximum total discount.
4. Never answer a payment plan, discount or scholarship question after only one search. Apply every limit and condition you found.
5. For calculations, write each step and double-check the arithmetic.
6. Use only what the search results say. If you can't find the answer, say so. Never guess.
7. Reply in the same language as the question.
8. No markdown formatting. Keep answers short and clear."""

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": "Search the university documents: course catalog, student handbook, "
                       "tuition and scholarships, FAQ and student services.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A short search query about one topic.",
                }
            },
            "required": ["query"],
        },
    },
}


@lru_cache(maxsize=1)
def get_db():
    if not config.DB_DIR.is_dir():
        raise RuntimeError(
            f"Database not found at {config.DB_DIR}. Run 'uv run python task.py' first."
        )
    return Chroma(
        persist_directory=str(config.DB_DIR),
        embedding_function=OpenRouterEmbeddings(),
    )


def search_documents(query, sources):
    """Search the database. Returns the chunks as text for the LLM and
    adds them to `sources` so the page can show them."""
    results = get_db().similarity_search(query, k=config.TOP_K + 2)

    # hide old documents, like the superseded tuition policy
    skip = config.SKIP_FILES_CONTAINING
    if skip:
        results = [r for r in results if skip not in r.metadata.get("source", "")]
    results = results[:config.TOP_K]

    if not results:
        return "No results found."

    texts = []
    for doc in results:
        file = Path(doc.metadata.get("source", "")).name
        page = doc.metadata.get("page")
        page = page + 1 if page is not None else None

        label = f"{file}, page {page}" if page else file
        texts.append(f"[{label}]\n{doc.page_content}")

        source = {
            "file": file,
            "page": page,
            "text": " ".join(doc.page_content.split())[:300],
        }
        if source not in sources:
            sources.append(source)

    return "\n\n---\n\n".join(texts)


def ask_llm(client, messages, use_tools):
    options = {
        "model": config.CHAT_MODEL,
        "messages": messages,
        "temperature": 0,
        "max_tokens": config.MAX_TOKENS,
    }
    if use_tools:
        options["tools"] = [SEARCH_TOOL]
    return client.chat.completions.create(**options).choices[0].message


def run_tool(call, steps, sources):
    if call.function.name != "search_documents":
        return f"Unknown tool: {call.function.name}"

    try:
        query = json.loads(call.function.arguments or "{}").get("query", "")
    except json.JSONDecodeError:
        return "The tool arguments were not valid JSON."

    steps.append({"action": "Searched", "input": query})
    return search_documents(query, sources)


def run_agent(question, history):
    """Returns (answer, steps, sources)."""
    client = get_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    messages.append({"role": "user", "content": question})

    steps = []    # what the agent did, shown on the page
    sources = []  # chunks it found

    for _ in range(config.MAX_STEPS):
        reply = ask_llm(client, messages, use_tools=True)

        # no tool call means the LLM is ready to answer
        if not reply.tool_calls:
            return reply.content or "", steps, sources

        messages.append(reply.model_dump(exclude_none=True))
        for call in reply.tool_calls:
            result = run_tool(call, steps, sources)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    # too many searches, so make it answer with what it has
    messages.append({
        "role": "user",
        "content": "Answer now using only what you already found.",
    })
    reply = ask_llm(client, messages, use_tools=False)
    return reply.content or "", steps, sources


def clean_history(raw):
    """Keep only real user/assistant messages from what the browser sent."""
    history = []
    for m in raw:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content"):
            history.append({"role": m["role"], "content": str(m["content"])})
    return history[-HISTORY_LIMIT:]


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return render_template("index.html", model=config.CHAT_MODEL)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/chat", methods=["POST"])
    def chat():
        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()
        if not question:
            return jsonify({"error": "Please type a question."}), 400

        history = clean_history(data.get("history", []))

        try:
            answer, steps, sources = run_agent(question, history)
        except RuntimeError as error:  # no API key or no database
            return jsonify({"error": str(error)}), 500
        except Exception as error:
            logger.exception("Agent failed")
            return jsonify({"error": f"Request failed: {error}"}), 500

        return jsonify({"answer": answer, "steps": steps, "sources": sources})

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
    