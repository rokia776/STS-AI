from fastapi import FastAPI

app = FastAPI(
    title="LLM Question Answering API",
    description="A simple LLM-powered Question Answering System",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "Welcome to LLM-QA API",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }s