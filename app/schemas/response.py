from pydantic import BaseModel


class QuestionResponse(BaseModel):
    question: str
    answer: str
    status: str