import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma

load_dotenv()

DB_DIR = "chroma_db"
API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"
CHAT_MODEL = "openai/gpt-4o-mini"  
TOP_K = 4

if not os.path.exists(DB_DIR):
    raise SystemExit("chroma_db not found. Run task3.py first.")

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

print("Ask a question about GlowDerma (type 'exit' to quit).\n")

while True:
    question = input("You: ").strip()
    if question.lower() in ("exit", "quit", "q", ""):
        break

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

    print("\nAnswer:", answer.content)
    pages = sorted({d.metadata["page"] + 1 for d in docs})
    print("Sources: pages", pages, "\n")