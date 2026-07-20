from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.vocabulary_agent import VocabularyAgent
from app.database import get_db
from app.schemas.requests import VocabularyGenerateRequest
from app.services.profile_service import get_profile
from app.services.vocabulary_service import save_vocabulary_items

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])
agent = VocabularyAgent()


@router.post("/generate")
def generate_vocabulary(payload: VocabularyGenerateRequest, db: Session = Depends(get_db)):
    profile = get_profile(db, payload.user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
    result = agent.generate(payload.topic, payload.count, profile.target_band)
    save_vocabulary_items(db, payload.user_id, payload.topic, result["items"])
    return result

