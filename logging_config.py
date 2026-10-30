import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """Log to the console and to logs/app.log (rotates at 5 MB, keeps 3 old files)."""
    LOG_DIR.mkdir(exist_ok=True)
    formatter = logging.Formatter(FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    file = RotatingFileHandler(LOG_DIR / "app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    file.setFormatter(formatter)

    logging.basicConfig(level=level, handlers=[console, file], force=True)

    # Keep noisy libraries quiet.
    for noisy in ("httpx", "httpcore", "openai", "pymongo", "pypdf"):
        logging.getLogger(noisy).setLevel(logging.WARNING)