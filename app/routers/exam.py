from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.requests import ExamVocabularyExplainRequest, ReadingExamSubmitRequest
from app.services.exam_service import ReadingExamService
from app.services.profile_service import get_profile

router = APIRouter(prefix="/exam", tags=["exam"])


@router.get("/reading/start")
def start_reading_exam():
    try:
        return ReadingExamService().exam()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/reading/submit")
def submit_reading_exam(payload: ReadingExamSubmitRequest, db: Session = Depends(get_db)):
    if get_profile(db, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
    return ReadingExamService().grade(payload.answers)


@router.post("/vocabulary/explain")
def explain_exam_vocabulary(payload: ExamVocabularyExplainRequest):
    try:
        return ReadingExamService().explain_vocabulary(payload.term, payload.section_index, payload.area)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
