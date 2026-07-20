from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ErrorEntry, KnowledgeQuestion, StudyPlan, StudyPlanDay, UploadedDocument, UserProfile, VocabularyItem
from app.schemas.profile import ProfileCreate
from app.services.document_service import safe_upload_dir


def create_profile(db: Session, payload: ProfileCreate) -> UserProfile:
    profile = UserProfile(
        current_band=payload.current_band,
        target_band=payload.target_band,
        prep_days=payload.prep_days,
        daily_minutes=payload.daily_minutes,
        weak_skills=",".join(payload.weak_skills),
        focus_areas=",".join(payload.focus_areas),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_profile(db: Session, user_id: int) -> UserProfile | None:
    return db.get(UserProfile, user_id)


def update_profile(db: Session, profile: UserProfile, payload: ProfileCreate) -> UserProfile:
    profile.current_band = payload.current_band
    profile.target_band = payload.target_band
    profile.prep_days = payload.prep_days
    profile.daily_minutes = payload.daily_minutes
    profile.weak_skills = ",".join(payload.weak_skills)
    profile.focus_areas = ",".join(payload.focus_areas)
    db.commit()
    db.refresh(profile)
    return profile


def delete_profile(db: Session, profile: UserProfile) -> None:
    documents = list(db.scalars(select(UploadedDocument).where(UploadedDocument.user_id == profile.id)))
    plan_ids = list(db.scalars(select(StudyPlan.id).where(StudyPlan.user_id == profile.id)))
    if plan_ids:
        db.execute(delete(StudyPlanDay).where(StudyPlanDay.plan_id.in_(plan_ids)))
    db.execute(delete(StudyPlan).where(StudyPlan.user_id == profile.id))
    db.execute(delete(KnowledgeQuestion).where(KnowledgeQuestion.user_id == profile.id))
    db.execute(delete(ErrorEntry).where(ErrorEntry.user_id == profile.id))
    db.execute(delete(VocabularyItem).where(VocabularyItem.user_id == profile.id))
    db.execute(delete(UploadedDocument).where(UploadedDocument.user_id == profile.id))
    db.delete(profile)
    db.commit()

    upload_dir = safe_upload_dir().resolve()
    for document in documents:
        file_path = (upload_dir / Path(document.stored_filename).name).resolve()
        if file_path.parent == upload_dir and file_path.exists():
            file_path.unlink()


def profile_to_context(profile: UserProfile) -> dict:
    return {
        "user_id": profile.id,
        "current_band": profile.current_band,
        "target_band": profile.target_band,
        "prep_days": profile.prep_days,
        "daily_minutes": profile.daily_minutes,
        "weak_skills": [x for x in profile.weak_skills.split(",") if x],
        "focus_areas": [x for x in profile.focus_areas.split(",") if x],
    }
