import logging

from fastapi import APIRouter, HTTPException

from app.schemas.question import QuestionRequest
from app.schemas.response import QuestionResponse
from app.services.llm_service import LLMServiceError, ask_llm
from app.models.question import save_question, get_all_questions
from app.core.redis_cache import cache_get, cache_set

logger = logging.getLogger("llm_qa")

router = APIRouter(prefix="/api/v1", tags=["Question"])

question_count = 0


@router.post("/question", response_model=QuestionResponse)
async def ask_question(payload: QuestionRequest):
    global question_count
    logger.info("Question received (length=%d)", len(payload.question))

    # Check cache first
    cache_key = f"question:{payload.question}"
    cached_answer = await cache_get(cache_key)
    if cached_answer:
        logger.info("Answer retrieved from cache")
        return QuestionResponse(
            question=payload.question,
            answer=cached_answer,
            status="success (cached)",
        )

    try:
        answer = ask_llm(payload.question)
    except LLMServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    question_count += 1
    logger.info("Question answered successfully (total=%d)", question_count)

    # Save to database
    await save_question(payload.question, answer, "success")

    # Cache the answer for 1 hour
    await cache_set(cache_key, answer, expire_seconds=3600)

    return QuestionResponse(
        question=payload.question,
        answer=answer,
        status="success",
    )


@router.post("/ask", response_model=QuestionResponse)
async def ask(payload: QuestionRequest):
    global question_count
    logger.info("Ask endpoint called (length=%d)", len(payload.question))

    # Check cache first
    cache_key = f"question:{payload.question}"
    cached_answer = await cache_get(cache_key)
    if cached_answer:
        logger.info("Answer retrieved from cache")
        return QuestionResponse(
            question=payload.question,
            answer=cached_answer,
            status="success (cached)",
        )

    try:
        answer = ask_llm(payload.question)
    except LLMServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    question_count += 1
    logger.info("Ask endpoint answered successfully (total=%d)", question_count)

    # Save to database
    await save_question(payload.question, answer, "success")

    # Cache the answer for 1 hour
    await cache_set(cache_key, answer, expire_seconds=3600)

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


@router.get("/questions")
async def get_questions(limit: int = 100):
    """Get all questions from the database."""
    logger.info("Get questions endpoint called")
    questions = await get_all_questions(limit)
    return {
        "count": len(questions),
        "questions": questions
    }
