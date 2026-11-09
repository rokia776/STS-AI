from pydantic import BaseModel, Field, field_validator


class QuestionRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Your question (3 to 1000 characters)",
        examples=["What is FastAPI?"],
    )

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question must not be empty or whitespace only")
        if len(value) < 3:
            raise ValueError("Question must be at least 3 characters long")
        return value