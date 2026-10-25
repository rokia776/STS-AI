"""Agentic RAG chatbot.

Instead of searching once, the LLM works like a small agent:
it decides when to search the documents, can search several times with
different queries, uses a calculator for math, and answers only when it
has enough information."""

import os
import ast
import json
import operator

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from langchain_core.embeddings import Embeddings
from langchain_chroma import Chroma

load_dotenv(override=True)

# Settings
DB_DIR = "chroma_db"
EMBED_MODEL = "baai/bge-m3"         
CHAT_MODEL = "openai/gpt-4o-mini"   
BASE_URL = "https://openrouter.ai/api/v1"
TOP_K = 4                         
MAX_STEPS = 5                       
MAX_TOKENS = 600
SKIP_FILES_CONTAINING = "SUPERSEDED"

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise SystemExit("OPENROUTER_API_KEY is missing. Add it to your .env file.")
if not os.path.isdir(DB_DIR):
    raise SystemExit(f"'{DB_DIR}' not found. Run task.py first to build the database.")

client = OpenAI(api_key=api_key, base_url=BASE_URL)


class OpenRouterEmbeddings(Embeddings):
    def embed_documents(self, texts):
        response = client.embeddings.create(model=EMBED_MODEL, input=texts)
        return [item.embedding for item in response.data]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


db = Chroma(persist_directory=DB_DIR, embedding_function=OpenRouterEmbeddings())



def search_documents(query, sources):
    """Search Chroma and return the chunks as text for the LLM.
    Every chunk found is also added to `sources` so the page can show it."""
    results = db.similarity_search(query, k=TOP_K + 2)

    # leave out files that are marked as old
    results = [
        doc for doc in results
        if SKIP_FILES_CONTAINING not in doc.metadata.get("source", "")
    ][:TOP_K]

    if not results:
        return "No results found."

    parts = []
    for doc in results:
        file = os.path.basename(doc.metadata.get("source", ""))
        page = doc.metadata.get("page")
        label = f"{file}, page {page + 1}" if page is not None else file
        parts.append(f"[{label}]\n{doc.page_content}")

        text = " ".join(doc.page_content.split())[:300]
        if not any(s["file"] == file and s["text"] == text for s in sources):
            sources.append({
                "file": file,
                "page": page + 1 if page is not None else None,
                "text": text,
            })

    return "\n\n---\n\n".join(parts)



OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
}


def evaluate(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](evaluate(node.left), evaluate(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](evaluate(node.operand))
    raise ValueError("unsupported expression")


def calculate(expression):
    try:
        result = evaluate(ast.parse(expression, mode="eval").body)
        return str(round(result, 2))
    except Exception:
        return "Error: could not calculate that expression."


# Description of the tools for the LLM
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Search the Horizon Delta University documents "
                           "(course catalog, student handbook, tuition and scholarships, FAQ, student services).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A short, specific search query about one topic.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Calculate a math expression, for example '14 * 4200 * 0.75 + 1900'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "The math expression."}
                },
                "required": ["expression"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are an assistant for Horizon Delta University. You have two tools: "
    "search_documents and calculate.\n"
    "How to work:\n"
    "1. Always search before answering a university question. Never answer from memory.\n"
    "2. If the question needs several facts, search separately for each fact "
    "with a short, specific query.\n"
    "3. For any question about money (tuition, fees, discounts, scholarships, installments, refunds), "
    "you MUST do all of these before answering:\n"
    "   a) search for the tuition rate and the fees,\n"
    "   b) search for the rules of every scholarship, discount, installment plan or refund mentioned in the question,\n"
    "   c) search for 'maximum total discount' or any other limit or condition that could apply.\n"
    "4. Never answer after only one search when the question mentions a payment plan, discount or scholarship. "
    "Apply every limit, cap and condition you found.\n"
    "5. Use calculate for every calculation. Do not do math in your head.\n"
    "6. Use only information from the search results. If you cannot find it, say you could not find it. Never guess.\n"
    "7. Reply in the same language as the question.\n"
    "8. Do not use markdown formatting. Keep the answer short and clear."
)

def run_agent(question, history):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history
    messages.append({"role": "user", "content": question})

    steps = []     # what the agent did, shown in the page
    sources = []   # chunks the agent found

    for _ in range(MAX_STEPS):
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            tools=TOOLS,
            temperature=0,
            max_tokens=MAX_TOKENS,
        )
        message = response.choices[0].message

        # no tool requested -> this is the final answer
        if not message.tool_calls:
            return message.content, steps, sources

        messages.append(message.model_dump(exclude_none=True))

        # run every tool the LLM asked for and give the results back
        for call in message.tool_calls:
            args = json.loads(call.function.arguments)

            if call.function.name == "search_documents":
                result = search_documents(args.get("query", ""), sources)
                steps.append({"action": "Searched", "input": args.get("query", "")})
            elif call.function.name == "calculate":
                result = calculate(args.get("expression", ""))
                steps.append({"action": "Calculated", "input": f"{args.get('expression', '')} = {result}"})
            else:
                result = "Unknown tool."

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            })

    # too many steps: ask for an answer with what it has
    messages.append({
        "role": "user",
        "content": "Answer now using only the information you already found.",
    })
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=0,
        max_tokens=MAX_TOKENS,
    )
    return response.choices[0].message.content, steps, sources


app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html", model=CHAT_MODEL)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Please type a question."}), 400

    # keep only the last few messages of the conversation
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in data.get("history", [])
        if m.get("role") in ("user", "assistant")
    ][-6:]

    try:
        answer, steps, sources = run_agent(question, history)
    except Exception as e:
        return jsonify({"error": f"Request failed: {e}"}), 500

    return jsonify({"answer": answer, "steps": steps, "sources": sources})


if __name__ == "__main__":
    app.run(debug=True)
