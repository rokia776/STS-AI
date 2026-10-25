import json
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

PDF_PATH = "data/GlowDerma_Skincare_Knowledge_Base_v1.0.pdf"
OUT_PATH = "data/chunks_report.txt"
JSON_PATH = "data/chunks.json"
CHUNK_SIZE = 900
CHUNK_OVERLAP = 200


def find_overlap(prev: str, nxt: str, max_len: int = 400) -> int:
    """Length of the longest suffix of prev that is also a prefix of nxt."""
    for k in range(min(len(prev), len(nxt), max_len), 9, -1):
        if prev[-k:] == nxt[:k]:
            return k
    return 0


pages = PyPDFLoader(PDF_PATH).load()
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)
chunks = splitter.split_documents(pages)

overlaps = [0]
for i in range(1, len(chunks)):
    same_page = chunks[i - 1].metadata["page"] == chunks[i].metadata["page"]
    overlaps.append(
        find_overlap(chunks[i - 1].page_content, chunks[i].page_content)
        if same_page else 0
    )

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(f"Pages: {len(pages)} | Chunks: {len(chunks)} | "
            f"chunk_size={CHUNK_SIZE} | overlap={CHUNK_OVERLAP}\n")
    f.write("Overlap with the previous chunk is wrapped in "
            "<<<OVERLAP ... OVERLAP>>>\n\n")

    for i, c in enumerate(chunks):
        text = c.page_content
        ov = overlaps[i]

        f.write("=" * 80 + "\n")
        f.write(f"CHUNK {i} | page {c.metadata['page'] + 1} | {len(text)} chars | "
                f"overlap with previous: {ov} chars\n")
        f.write("=" * 80 + "\n")
        if ov:
            f.write(f"<<<OVERLAP\n{text[:ov]}\nOVERLAP>>>\n{text[ov:]}\n\n")
        else:
            f.write(text + "\n\n")

print(f"Saved {len(chunks)} chunks to {OUT_PATH}")

with open(JSON_PATH, "w", encoding="utf-8") as f:
    json.dump(
        [
            {
                "id": i,
                "page": c.metadata["page"] + 1,
                "overlap_with_previous": overlaps[i],
                "overlap_text": c.page_content[:overlaps[i]],
                "text": c.page_content,
            }
            for i, c in enumerate(chunks)
        ],
        f, ensure_ascii=False, indent=2,
    )

print(f"Updated {JSON_PATH}")