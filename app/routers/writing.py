from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.writing_coach_agent import WritingCoachAgent
from app.database import get_db
from app.schemas.requests import WritingReviewRequest
from app.services.error_notebook_service import add_error, summarize_errors
from app.services.profile_service import get_profile
from app.services.rag_service import RagService

router = APIRouter(prefix="/writing", tags=["writing"])
agent = WritingCoachAgent()
rag = RagService()


@router.post("/review")
def review_writing(payload: WritingReviewRequest, db: Session = Depends(get_db)):
    if get_profile(db, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
    historical = summarize_errors(db, payload.user_id)
    result = agent.review(payload.essay_text, payload.task_type, historical)
    saved = result["saved_error"]
    add_error(db, payload.user_id, "writing", saved["category"], saved["original_text"], saved["feedback"], saved["suggestion"])
    result["rag_context"] = rag.retrieve("IELTS writing coherence task response grammar", top_k=2)
    return result

