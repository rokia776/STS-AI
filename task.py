"""Reads files from data/, splits them into chunks (showing the overlap),
embeds them with OpenRouter, stores them in Chroma and runs a test search."""

import os
import json
import shutil

from dotenv import load_dotenv
from openai import OpenAI
from langchain_core.embeddings import Embeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

load_dotenv(override=True)
# Settings
DATA_DIR = "data"
DB_DIR = "chroma_db"
OUTPUT_DIR = "output"
CHUNK_SIZE = 1500
CHUNK_OVERLAP =300
EMBED_MODEL = "baai/bge-m3"
BASE_URL = "https://openrouter.ai/api/v1"
BATCH_SIZE = 64

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise SystemExit("OPENROUTER_API_KEY is missing. Add it to your .env file.")
if not os.path.isdir(DATA_DIR):
    raise SystemExit(f"Folder '{DATA_DIR}' not found.")


class OpenRouterEmbeddings(Embeddings):
    """Small wrapper that sends the texts to OpenRouter."""

    def __init__(self):
        self.client = OpenAI(api_key=api_key, base_url=BASE_URL)

    def embed_documents(self, texts):
        response = self.client.embeddings.create(model=EMBED_MODEL, input=texts)
        return [item.embedding for item in response.data]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def load_documents(folder):
    """Load every PDF, TXT and MD file in the folder."""
    docs = []
    for root, _, files in os.walk(folder):
        for name in sorted(files):
            path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()

            if ext == ".pdf":
                pages = PyPDFLoader(path).load()
            elif ext in (".txt", ".md"):
                pages = TextLoader(path, encoding="utf-8").load()
            else:
                continue

            # skip empty pages
            pages = [p for p in pages if p.page_content.strip()]
            docs.extend(pages)
            print(f"  {name}: {len(pages)} page(s)")
    return docs


def get_overlap(prev_text, current_text):
    """Return the text at the end of the previous chunk
    that is repeated at the start of the current chunk."""
    for size in range(min(len(prev_text), len(current_text)), 9, -1):
        if prev_text.endswith(current_text[:size]):
            return current_text[:size]
    return ""


# 1. Load files
print("Loading files...")
docs = load_documents(DATA_DIR)
if not docs:
    raise SystemExit("No PDF, TXT or MD files found in the data folder.")

# 2. Split into chunks
print("\nSplitting into chunks...")
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)
chunks = splitter.split_documents(docs)
print(f"  {len(chunks)} chunks created")

# 3. Find the overlap between each chunk and the one before it
overlaps = [""]  # the first chunk has no previous chunk
for i in range(1, len(chunks)):
    # chunks are only split inside the same page, so compare same page only
    if chunks[i - 1].metadata == chunks[i].metadata:
        overlaps.append(get_overlap(chunks[i - 1].page_content, chunks[i].page_content))
    else:
        overlaps.append("")

print("\nOverlap between chunks:")
for i, overlap in enumerate(overlaps):
    if overlap:
        print(f"\n  Chunk {i - 1} -> Chunk {i} ({len(overlap)} chars)")
        print(f"  {overlap!r}")

# Save the chunks (with their overlap) so they can be inspected later
os.makedirs(OUTPUT_DIR, exist_ok=True)
chunk_data = []
for i, chunk in enumerate(chunks):
    chunk_data.append({
        "id": i,
        "source": os.path.basename(chunk.metadata["source"]),
        "page": chunk.metadata.get("page"),
        "overlap_with_previous": overlaps[i],
        "text": chunk.page_content,
    })
with open(os.path.join(OUTPUT_DIR, "chunks.json"), "w", encoding="utf-8") as f:
    json.dump(chunk_data, f, ensure_ascii=False, indent=2)

# 4. Store in Chroma (start fresh each run)
print("\nEmbedding chunks and saving to Chroma...")
embeddings = OpenRouterEmbeddings()

if os.path.exists(DB_DIR):
    shutil.rmtree(DB_DIR)

db = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
for i in range(0, len(chunks), BATCH_SIZE):
    db.add_documents(chunks[i:i + BATCH_SIZE])
    print(f"  {min(i + BATCH_SIZE, len(chunks))}/{len(chunks)}")
