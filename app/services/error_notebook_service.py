from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ErrorEntry


def add_error(
    db: Session,
    user_id: int,
    source: str,
    category: str,
    original_text: str,
    feedback: str,
    suggestion: str,
) -> ErrorEntry:
    entry = ErrorEntry(
        user_id=user_id,
        source=source,
        category=category,
        original_text=original_text,
        feedback=feedback,
        suggestion=suggestion,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_errors(db: Session, user_id: int) -> list[ErrorEntry]:
    return list(db.scalars(select(ErrorEntry).where(ErrorEntry.user_id == user_id).order_by(ErrorEntry.created_at.desc())))


def summarize_errors(db: Session, user_id: int) -> list[dict]:
    return [
        {
            "source": item.source,
            "category": item.category,
            "feedback": item.feedback,
            "suggestion": item.suggestion,
        }
        for item in list_errors(db, user_id)[:8]
    ]

