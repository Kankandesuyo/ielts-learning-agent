from typing import Literal

from pydantic import BaseModel, Field


class UserIdRequest(BaseModel):
    user_id: int = Field(..., ge=1)


class StudyPlanRequest(UserIdRequest):
    days: int | None = Field(default=None, ge=1, le=90)


class PlanDayStatusRequest(BaseModel):
    completed: bool


class WritingReviewRequest(UserIdRequest):
    essay_text: str = Field(..., min_length=30, max_length=20_000)
    task_type: str | None = Field(default=None, pattern=r"^Task [12]$", description="Task 1 or Task 2 if known.")


class SpeakingPracticeRequest(UserIdRequest):
    part: int = Field(default=1, ge=1, le=3)
    answer_text: str | None = Field(default=None, max_length=5_000)
    topic: str | None = Field(default=None, max_length=120)


class ReadingPracticeRequest(UserIdRequest):
    question_type: str | None = Field(default=None, max_length=100)
    user_answer: str | None = Field(default=None, max_length=2_000)


class ListeningPracticeRequest(UserIdRequest):
    scenario: str | None = Field(default=None, max_length=100)
    user_answer: str | None = Field(default=None, max_length=2_000)


class VocabularyGenerateRequest(UserIdRequest):
    topic: str = Field(default="education", max_length=100)
    count: int = Field(default=8, ge=1, le=30)


class SupervisorCoachRequest(UserIdRequest):
    skill_focus: str | None = Field(default=None, pattern=r"^(listening|speaking|reading|writing)$", description="Optional IELTS skill.")
    learner_input: str | None = Field(default=None, max_length=20_000, description="Optional answer or essay text for the selected skill.")
    task_type: str | None = Field(default=None, pattern=r"^Task [12]$", description="Writing only: Task 1 or Task 2.")
    speaking_part: int = Field(default=1, ge=1, le=3)


class KnowledgeQuestionRequest(UserIdRequest):
    skill: str = Field(default="auto", pattern="^(auto|reading|listening|vocabulary|writing)$")
    topic: str | None = Field(default=None, max_length=100)


class KnowledgeAnswerRequest(UserIdRequest):
    question_id: int = Field(..., ge=1)
    answer: str = Field(..., min_length=1, max_length=10000)


class ReadingExamSubmitRequest(UserIdRequest):
    answers: dict[str, str]


class ExamVocabularyExplainRequest(BaseModel):
    """A short selection from a source-backed exam question or passage.

    The browser sends only the selected term and section number. The server
    rebuilds the surrounding context from the PDF instead of trusting text
    supplied by the client.
    """

    term: str = Field(..., min_length=1, max_length=80, pattern=r"^[A-Za-z][A-Za-z' -]*$")
    section_index: int = Field(..., ge=0, le=2)
    area: Literal["questions", "passage"] = "questions"
