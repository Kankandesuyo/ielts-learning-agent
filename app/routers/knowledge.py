import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.writing_coach_agent import WritingCoachAgent
from app.database import get_db
from app.schemas.requests import KnowledgeAnswerRequest, KnowledgeQuestionRequest
from app.services.error_notebook_service import add_error, summarize_errors
from app.services.knowledge_service import KnowledgeService
from app.services.profile_service import get_profile

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
knowledge = KnowledgeService()
writing_agent = WritingCoachAgent()


@router.get("/status")
def knowledge_status():
    return knowledge.status()


@router.post("/index")
def rebuild_knowledge_index(force: bool = False):
    return knowledge.build_index(force=force)


@router.post("/question")
def generate_knowledge_question(payload: KnowledgeQuestionRequest, db: Session = Depends(get_db)):
    profile = get_profile(db, payload.user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
    skill = payload.skill
    if skill == "auto":
        weak = [item.strip().lower() for item in profile.weak_skills.split(",") if item.strip()]
        supported = [item for item in weak if item in {"reading", "listening", "writing"}]
        skill = supported[0] if supported else "reading"
    try:
        item = knowledge.create_question(db, payload.user_id, skill, payload.topic)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return knowledge.public_question(item)


@router.post("/analyze")
def analyze_knowledge_answer(payload: KnowledgeAnswerRequest, db: Session = Depends(get_db)):
    item = knowledge.get_question(db, payload.question_id, payload.user_id)
    if item is None:
        raise HTTPException(status_code=404, detail="题目不存在或不属于当前用户。")

    source = {"book": item.source, "page": item.page}
    if item.skill == "writing":
        result = writing_agent.review(payload.answer, "Task 1" if "graph" in item.question.lower() else "Task 2", summarize_errors(db, payload.user_id))
        result.update({"question_id": item.id, "source": source, "grounding_note": item.explanation})
        saved = result["saved_error"]
        add_error(db, payload.user_id, "writing", saved["category"], saved["original_text"], saved["feedback"], saved["suggestion"])
        return result

    normalize = lambda value: re.sub(r"[^a-z0-9]", "", value.lower())
    correct = normalize(payload.answer) == normalize(item.correct_answer)
    analysis = {
        "question_id": item.id,
        "skill": item.skill,
        "correct": correct,
        "your_answer": payload.answer,
        "correct_answer": item.correct_answer,
        "explanation": item.explanation,
        "source": source,
        "next_step": "答对了：记下这个词在原句中的搭配。" if correct else "返回原文定位该词，抄写完整句子后再做一道。",
    }
    if not correct:
        add_error(db, payload.user_id, item.skill, "source_cloze", payload.answer, item.explanation, analysis["next_step"])
    return analysis
