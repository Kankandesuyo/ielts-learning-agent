from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.reading_coach_agent import ReadingCoachAgent
from app.database import get_db
from app.schemas.requests import ReadingPracticeRequest
from app.services.error_notebook_service import add_error
from app.services.profile_service import get_profile

router = APIRouter(prefix="/reading", tags=["reading"])
agent = ReadingCoachAgent()


@router.post("/practice")
def reading_practice(payload: ReadingPracticeRequest, db: Session = Depends(get_db)):
    if get_profile(db, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
    result = agent.practice(payload.question_type, payload.user_answer)
    if payload.user_answer and not result["correct"]:
        add_error(db, payload.user_id, "reading", "locating_words", payload.user_answer, result["explanation"], result["trap"])
    return result

