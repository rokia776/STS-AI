import logging

from fastapi import APIRouter

from app.schemas.question import QuestionRequest
from app.schemas.response import QuestionResponse

logger = logging.getLogger("llm_qa")

router = APIRouter(prefix="/api/v1", tags=["Question"])


@router.post("/question", response_model=QuestionResponse)
def ask_question(payload: QuestionRequest):
    logger.info("Question received (length=%d)", len(payload.question))

    # Placeholder: the LLM will be connected in the next step
    answer = "LLM not connected yet"

    logger.info("Question answered successfully")
    return QuestionResponse(
        question=payload.question,
        answer=answer,
        status="success",
    )