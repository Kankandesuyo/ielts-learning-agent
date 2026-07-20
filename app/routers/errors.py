from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.error_notebook_service import list_errors

router = APIRouter(prefix="/errors", tags=["errors"])


@router.get("/{user_id}")
def get_errors(user_id: int, db: Session = Depends(get_db)):
    return {
        "user_id": user_id,
        "items": [
            {
                "id": item.id,
                "source": item.source,
                "category": item.category,
                "original_text": item.original_text,
                "feedback": item.feedback,
                "suggestion": item.suggestion,
                "created_at": item.created_at.isoformat(),
            }
            for item in list_errors(db, user_id)
        ],
        "next_step": "Pick the most frequent category and do a 20-minute focused drill.",
    }

