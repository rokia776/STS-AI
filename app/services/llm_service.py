import logging

from app.services import flan_backend

logger = logging.getLogger("llm_qa")


class LLMServiceError(Exception):
    """Raised when the local model fails."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def ask_llm(question: str) -> str:
    try:
        logger.info("Sending question to local model")
        answer = flan_backend.generate(question)
        logger.info("Model answered (length=%d)", len(answer))
        return answer or "No answer generated."
    except ImportError:
        logger.error("transformers/torch are not installed")
        raise LLMServiceError("Model dependencies are not installed", 500)
    except Exception as exc:
        logger.exception("Model error: %s", exc)
        raise LLMServiceError("Model failed to generate an answer", 500)