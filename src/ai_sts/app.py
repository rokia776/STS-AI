import os
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma

load_dotenv()

DB_DIR = "chroma_db"
API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"
CHAT_MODEL = "openai/gpt-4o-mini"
TOP_K = 4

if not API_KEY:
    raise SystemExit("OPENROUTER_API_KEY is missing. Add it to your .env file.")
if not os.path.exists(DB_DIR):
    raise SystemExit("chroma_db not found. Run task3.py first (from the AI sts folder).")

embeddings = OpenAIEmbeddings(
    model="baai/bge-m3",
    api_key=API_KEY,
    base_url=BASE_URL,
    check_embedding_ctx_length=False,
)
vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)

llm = ChatOpenAI(
    model=CHAT_MODEL,
    api_key=API_KEY,
    base_url=BASE_URL,
    temperature=0,
)

SYSTEM_PROMPT = (
    "You are a GlowDerma skincare assistant. Answer ONLY using the context below. "
    "If the answer is not in the context, say you don't have that information. "
    "Answer in the same language as the question.\n\nContext:\n{context}"
)

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/ask")
def ask():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify(error="Type a question first."), 400

    try:
        docs = vectorstore.similarity_search(question, k=TOP_K)
        context = "\n\n---\n\n".join(
            f"[page {d.metadata['page'] + 1}]\n{d.page_content}" for d in docs
        )
        answer = llm.invoke(
            [
                ("system", SYSTEM_PROMPT.format(context=context)),
                ("human", question),
            ]
        )
    except Exception as e:
        return jsonify(error=f"The request failed: {e}"), 500

    return jsonify(
        answer=answer.content,
        pages=sorted({d.metadata["page"] + 1 for d in docs}),
        passages=[
            {"page": d.metadata["page"] + 1, "text": d.page_content} for d in docs
        ],
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)