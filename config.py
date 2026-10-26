"""All settings live here.

Values come from environment variables (or the .env file) and have safe
defaults. No secret is stored in the code."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent

# override=True so the .env file wins over an old key saved in the system
load_dotenv(PROJECT_ROOT / ".env", override=True)


def _path(name, default):
    """Read a folder setting. Relative paths are relative to the project folder."""
    path = Path(os.getenv(name, default))
    return path if path.is_absolute() else PROJECT_ROOT / path


# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
CHAT_MODEL = os.getenv("CHAT_MODEL", "openai/gpt-4o-mini")  # must support tool calling
EMBED_MODEL = os.getenv("EMBED_MODEL", "baai/bge-m3")

# Folders
DATA_DIR = _path("DATA_DIR", "data")
DB_DIR = _path("DB_DIR", "chroma_db")
OUTPUT_DIR = _path("OUTPUT_DIR", "output")

# Chunking
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "300"))

# Agent
TOP_K = int(os.getenv("TOP_K", "4"))              # chunks returned by each search
MAX_STEPS = int(os.getenv("MAX_STEPS", "6"))      # max tool rounds before the agent must answer
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "600"))  # max length of each LLM reply
SKIP_FILES_CONTAINING = os.getenv("SKIP_FILES_CONTAINING", "SUPERSEDED")  # empty = skip nothing

# Web server
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")


def require_api_key():
    """Return the API key, or raise a clear error if it is missing."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is missing. Copy .env.example to .env and add your key."
        )
    return OPENROUTER_API_KEY