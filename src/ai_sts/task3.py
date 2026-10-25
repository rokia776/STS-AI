import os
import json
import shutil
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

load_dotenv()

PDF_PATH = "data/GlowDerma_Skincare_Knowledge_Base_v1.0.pdf"
DB_DIR = "chroma_db"

pages = PyPDFLoader(PDF_PATH).load()
print("Pages loaded:", len(pages))

splitter = RecursiveCharacterTextSplitter(
    chunk_size=900,
    chunk_overlap=150,
    separators=["\n\n", "\n", ". ", " ", ""],
)
chunks = splitter.split_documents(pages)
print("Total chunks:", len(chunks))

with open("data/chunks.json", "w", encoding="utf-8") as f:
    json.dump(
        [{"id": i, "page": c.metadata["page"] + 1, "text": c.page_content}
         for i, c in enumerate(chunks)],
        f, ensure_ascii=False, indent=2,
    )

embeddings = OpenAIEmbeddings(
    model="baai/bge-m3",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    check_embedding_ctx_length=False,
)

if os.path.exists(DB_DIR):
    shutil.rmtree(DB_DIR) 

vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory=DB_DIR,
)
print("Stored in Chroma:", vectorstore._collection.count(), "chunks")