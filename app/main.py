from fastapi import FastAPI
from app.core.logging_config import setup_logging
from app.api.v1.question import router as question_router
logger = setup_logging()

app = FastAPI(
    title="LLM Question Answering API",
    description="A simple LLM-powered Question Answering System",
    version="1.0.0",
)

app.include_router(question_router)


@app.get("/")
def root():
    logger.info("Root endpoint was accessed")
    return {"message": "Welcome to LLM-QA API"}


@app.get("/health")
def health_check():
    logger.info("Health check requested")
    return {"status": "healthy"}