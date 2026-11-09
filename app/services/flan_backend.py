import logging
import threading

from app.core.config import settings

logger = logging.getLogger("llm_qa")

_lock = threading.Lock()
_tokenizer = None
_model = None


def _load_model():
    global _tokenizer, _model
    if _model is not None:
        return

    with _lock:
        if _model is not None:
            return

        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        logger.info("Loading model %s (first request only)", settings.FLAN_MODEL)
        _tokenizer = AutoTokenizer.from_pretrained(settings.FLAN_MODEL)
        _model = AutoModelForSeq2SeqLM.from_pretrained(settings.FLAN_MODEL)
        _model.eval()
        logger.info("Model loaded successfully")


def generate(prompt: str) -> str:
    _load_model()

    inputs = _tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )
    outputs = _model.generate(
        **inputs,
        max_new_tokens=settings.FLAN_MAX_NEW_TOKENS,
    )
    return _tokenizer.decode(outputs[0], skip_special_tokens=True).strip()