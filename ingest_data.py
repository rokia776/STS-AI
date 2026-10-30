"""Load every PDF in the data/ folder into SQLite.

Usage:  python ingest_data.py            (uses ./data)
        python ingest_data.py my_folder
"""
import sys
from pathlib import Path

from fastapi import HTTPException

from main import ingest_pdf, create_indexes, logger


def run(folder: str = "data") -> None:
    create_indexes()
    pdfs = sorted(p for p in Path(folder).rglob("*") if p.suffix.lower() == ".pdf")
    if not pdfs:
        logger.warning("No PDF files found in '%s'", folder)
        return

    done = skipped = failed = 0
    for i, pdf in enumerate(pdfs, 1):
        logger.info("[%d/%d] %s", i, len(pdfs), pdf.name)
        try:
            result = ingest_pdf(pdf.name, pdf.read_bytes())
            if result.get("already_exists"):
                skipped += 1
            else:
                done += 1
        except HTTPException as exc:
            failed += 1
            logger.error("Skipped %s: %s", pdf.name, exc.detail)
        except Exception:
            failed += 1
            logger.exception("Failed on %s", pdf.name)

    logger.info("Finished: %d ingested, %d already existed, %d failed", done, skipped, failed)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "data")