from pydantic import BaseModel, Field


class ApiMessage(BaseModel):
    message: str


class NextStep(BaseModel):
    next_step: str = Field(..., description="Concrete action the student should do next.")

