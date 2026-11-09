import logging

from fastapi import APIRouter, HTTPException

from app.schemas.question import QuestionRequest
from app.schemas.response import QuestionResponse
from app.services.llm_service import LLMServiceError, ask_llm

logger = logging.getLogger("llm_qa")

router = APIRouter(prefix="/api/v1", tags=["Question"])


@router.post("/question", response_model=QuestionResponse)
def ask_question(payload: QuestionRequest):
    logger.info("Question received (length=%d)", len(payload.question))

    try:
        answer = ask_llm(payload.question)
    except LLMServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    logger.info("Question answered successfully")
    return QuestionResponse(
        question=payload.question,
        answer=answer,
        status="success",
    )