from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    """Return naive UTC for SQLite while avoiding deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    current_band: Mapped[float] = mapped_column(Float)
    target_band: Mapped[float] = mapped_column(Float)
    prep_days: Mapped[int] = mapped_column(Integer)
    daily_minutes: Mapped[int] = mapped_column(Integer)
    weak_skills: Mapped[str] = mapped_column(String(255))
    focus_areas: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AuthAccount(Base):
    """Login identity kept separate from the learner profile.

    This lets an account exist before onboarding is complete, while profile_id
    provides the server-side ownership boundary for all learning data.
    """

    __tablename__ = "auth_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("user_profiles.id"), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AuthSession(Base):
    """A revocable server-side session; the raw token is never stored."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("auth_accounts.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ErrorEntry(Base):
    __tablename__ = "error_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), index=True)
    source: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(100))
    original_text: Mapped[str] = mapped_column(Text)
    feedback: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class VocabularyItem(Base):
    __tablename__ = "vocabulary_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), index=True)
    word: Mapped[str] = mapped_column(String(100), index=True)
    topic: Mapped[str] = mapped_column(String(100))
    meaning: Mapped[str] = mapped_column(Text)
    example_sentence: Mapped[str] = mapped_column(Text)
    collocation: Mapped[str] = mapped_column(Text)
    ielts_usage: Mapped[str] = mapped_column(Text)
    mastery_level: Mapped[int] = mapped_column(Integer, default=0)
    next_review_day: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    content_type: Mapped[str] = mapped_column(String(120))
    file_size: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(80), default="general")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class KnowledgeQuestion(Base):
    __tablename__ = "knowledge_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), index=True)
    skill: Mapped[str] = mapped_column(String(30), index=True)
    question_type: Mapped[str] = mapped_column(String(40))
    question: Mapped[str] = mapped_column(Text)
    passage: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(255))
    page: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), index=True)
    days: Mapped[int] = mapped_column(Integer)
    estimated_goal_gap: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class StudyPlanDay(Base):
    __tablename__ = "study_plan_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("study_plans.id"), index=True)
    day_number: Mapped[int] = mapped_column(Integer)
    task_json: Mapped[str] = mapped_column(Text)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
