"""Builds the vector database.

read files then  split into chunks then embed then store in Chroma.
Run it with:  uv run python task.py"""

import json
import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config
from embeddings import OpenRouterEmbeddings

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}
BATCH_SIZE = 64  # chunks sent to the embedding model at once


def load_documents(folder):
    """Load every PDF, TXT and MD file in the folder (and its subfolders)."""
    docs = []
    for path in sorted(Path(folder).rglob("*")):
        extension = path.suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            continue

        if extension == ".pdf":
            pages = PyPDFLoader(str(path)).load()
        else:
            pages = TextLoader(str(path), encoding="utf-8").load()

        pages = [page for page in pages if page.page_content.strip()]  # skip empty pages
        docs.extend(pages)
        print(f"  {path.name}: {len(pages)} page(s)")
    return docs


def split_documents(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    return splitter.split_documents(docs)


def get_overlap(previous_text, current_text, min_length=10):
    """Return the text at the end of the previous chunk that is repeated
    at the start of the current chunk (empty string if there is none)."""
    longest = min(len(previous_text), len(current_text))
    for size in range(longest, min_length - 1, -1):
        if previous_text.endswith(current_text[:size]):
            return current_text[:size]
    return ""


def find_overlaps(chunks):
    """One overlap string per chunk. The first chunk of a page has none,
    because the splitter works inside one page at a time."""
    overlaps = [""]
    for i in range(1, len(chunks)):
        if chunks[i - 1].metadata == chunks[i].metadata:
            overlaps.append(get_overlap(chunks[i - 1].page_content, chunks[i].page_content))
        else:
            overlaps.append("")
    return overlaps[: len(chunks)]


def save_chunks(chunks, overlaps):
    """Save every chunk (and its overlap) to a JSON file so it can be inspected."""
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = []
    for i, chunk in enumerate(chunks):
        page = chunk.metadata.get("page")
        data.append({
            "id": i,
            "source": Path(chunk.metadata["source"]).name,
            "page": page + 1 if page is not None else None,
            "overlap_with_previous": overlaps[i],
            "text": chunk.page_content,
        })
    output_file = config.OUTPUT_DIR / "chunks.json"
    output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_file


def build_database(chunks):
    """Create a fresh Chroma database from the chunks."""
    if config.DB_DIR.exists():
        try:
            shutil.rmtree(config.DB_DIR)
        except PermissionError:
            raise SystemExit(
                f"Cannot delete {config.DB_DIR}. Stop the chatbot (app.py) and try again."
            )

    db = Chroma(
        persist_directory=str(config.DB_DIR),
        embedding_function=OpenRouterEmbeddings(),
    )
    for start in range(0, len(chunks), BATCH_SIZE):
        db.add_documents(chunks[start:start + BATCH_SIZE])
        print(f"  {min(start + BATCH_SIZE, len(chunks))}/{len(chunks)}")


def main():
    try:
        config.require_api_key()
    except RuntimeError as error:
        raise SystemExit(str(error))

    if not config.DATA_DIR.is_dir():
        raise SystemExit(f"Folder not found: {config.DATA_DIR}")

    print("Loading files...")
    docs = load_documents(config.DATA_DIR)
    if not docs:
        raise SystemExit(f"No PDF, TXT or MD files found in {config.DATA_DIR}")

    print("Splitting into chunks...")
    chunks = split_documents(docs)
    overlaps = find_overlaps(chunks)
    output_file = save_chunks(chunks, overlaps)
    print(f"  {len(chunks)} chunks ({sum(1 for o in overlaps if o)} with overlap)")
    print(f"  saved to {output_file}")

    print("Embedding chunks and saving to Chroma...")
    build_database(chunks)

    print(f"Done. Database saved in {config.DB_DIR}")
    print("Restart the chatbot if it is running.")


if __name__ == "__main__":
    main()
