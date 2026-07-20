from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.listening_coach_agent import ListeningCoachAgent
from app.database import get_db
from app.schemas.requests import ListeningPracticeRequest
from app.services.error_notebook_service import add_error
from app.services.profile_service import get_profile

router = APIRouter(prefix="/listening", tags=["listening"])
agent = ListeningCoachAgent()


@router.post("/practice")
def listening_practice(payload: ListeningPracticeRequest, db: Session = Depends(get_db)):
    if get_profile(db, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
    result = agent.practice(payload.scenario, payload.user_answer)
    if payload.user_answer and not result["correct"]:
        add_error(db, payload.user_id, "listening", "synonym_trap", payload.user_answer, result["keyword_explanation"], result["trap"])
    return result

