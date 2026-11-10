from fastapi import FastAPI
from app.core.logging_config import setup_logging
from app.api.v1.question import router as question_router
from app.core.database import get_pool, close_pool
from app.models.question import create_questions_table
logger = setup_logging()

app = FastAPI(
    title="LLM Question Answering API",
    description="A simple LLM-powered Question Answering System",
    version="1.0.0",
)

app.include_router(question_router)


@app.on_event("startup")
async def startup_event():
    """Initialize database connection pool and create tables."""
    await get_pool()
    await create_questions_table()
    logger.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection pool."""
    await close_pool()
    logger.info("Application shutdown complete")


@app.get("/")
def root():
    logger.info("Root endpoint was accessed")
    return {"message": "Welcome to LLM-QA API"}


@app.get("/health")
def health_check():
    logger.info("Health check requested")
    return {"status": "healthy"}