from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.speaking_coach_agent import SpeakingCoachAgent
from app.database import get_db
from app.schemas.requests import SpeakingPracticeRequest
from app.services.error_notebook_service import add_error, summarize_errors
from app.services.profile_service import get_profile

router = APIRouter(prefix="/speaking", tags=["speaking"])
agent = SpeakingCoachAgent()


@router.post("/practice")
def speaking_practice(payload: SpeakingPracticeRequest, db: Session = Depends(get_db)):
    if get_profile(db, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
    result = agent.practice(payload.part, payload.answer_text, payload.topic, summarize_errors(db, payload.user_id))
    if "saved_error" in result:
        saved = result["saved_error"]
        add_error(db, payload.user_id, "speaking", saved["category"], saved["original_text"], saved["feedback"], saved["suggestion"])
    return result

