"""Re-run title/entity extraction ONLY for papers that currently have no entities.

Usage:  uv run python fix_entities.py
Safe to run many times. Does not touch chunks or embeddings.
"""
import json
import time

from main import (CHUNK_OVERLAP, CHUNK_SIZE, RELATION_BY_TYPE, create_indexes, db,
                  extract_metadata, logger)

STEP = CHUNK_SIZE - CHUNK_OVERLAP


def paper_text(c, paper_id: str, max_chars: int = 14000) -> str:
    rows = c.execute("SELECT text FROM chunks WHERE paper_id=? ORDER BY chunk_index",
                     (paper_id,)).fetchall()
    # drop the overlap so the text is not duplicated
    return "".join(r["text"][:STEP] for r in rows)[:max_chars]


def run():
    create_indexes()
    with db() as c:
        todo = c.execute(
            "SELECT p.paper_id, p.filename FROM papers p "
            "WHERE NOT EXISTS (SELECT 1 FROM edges e WHERE e.paper_id = p.paper_id) "
            "ORDER BY p.filename").fetchall()
    if not todo:
        logger.info("Every paper already has entities. Nothing to do.")
        return
    logger.info("%d papers have no entities", len(todo))

    fixed = still_failed = 0
    for i, row in enumerate(todo, 1):
        with db() as c:
            text = paper_text(c, row["paper_id"])
        meta = extract_metadata(text, row["filename"])
        ents = [e for e in (meta.get("entities") or [])
                if isinstance(e, dict) and str(e.get("name") or "").strip()]
        if not ents:
            still_failed += 1
            logger.warning("[%d/%d] still no entities: %s", i, len(todo), row["filename"])
            time.sleep(2)
            continue

        with db() as c:
            c.execute("UPDATE papers SET title=?, authors=?, year=? WHERE paper_id=?",
                      (str(meta.get("title") or row["filename"]),
                       json.dumps(meta.get("authors") or []), meta.get("year"), row["paper_id"]))
            for ent in ents:
                name = ent["name"].strip()
                etype = str(ent.get("type") or "CONCEPT").upper()
                c.execute("INSERT OR IGNORE INTO entities (canonical_name, name, type) VALUES (?,?,?)",
                          (name.lower(), name, etype))
                eid = c.execute("SELECT id FROM entities WHERE canonical_name=?",
                                (name.lower(),)).fetchone()["id"]
                c.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?)",
                          (row["paper_id"], eid, RELATION_BY_TYPE.get(etype, "MENTIONS")))
        fixed += 1
        logger.info("[%d/%d] fixed %s (%d entities)", i, len(todo), row["filename"], len(ents))

    logger.info("Finished: %d fixed, %d still without entities", fixed, still_failed)


if __name__ == "__main__":
    run()