import logging

from fastapi import APIRouter, HTTPException

from app.schemas.question import QuestionRequest
from app.schemas.response import QuestionResponse
from app.services.llm_service import LLMServiceError, ask_llm

logger = logging.getLogger("llm_qa")

router = APIRouter(prefix="/api/v1", tags=["Question"])

question_count = 0


@router.post("/question", response_model=QuestionResponse)
def ask_question(payload: QuestionRequest):
    global question_count
    logger.info("Question received (length=%d)", len(payload.question))

    try:
        answer = ask_llm(payload.question)
    except LLMServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    question_count += 1
    logger.info("Question answered successfully (total=%d)", question_count)
    return QuestionResponse(
        question=payload.question,
        answer=answer,
        status="success",
    )


@router.get("/stats")
def get_stats():
    logger.info("Stats endpoint was accessed")
    return {
        "total_questions_processed": question_count,
        "api_version": "1.0.0",
        "status": "operational"
    }