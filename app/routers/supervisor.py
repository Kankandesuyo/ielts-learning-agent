from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.supervisor_agent import SupervisorAgent
from app.database import get_db
from app.schemas.requests import SupervisorCoachRequest, UserIdRequest
from app.services.error_notebook_service import add_error, summarize_errors
from app.services.profile_service import get_profile, profile_to_context
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/supervisor", tags=["supervisor"])
agent = SupervisorAgent()
knowledge = KnowledgeService()


@router.post("/diagnose")
def diagnose_learning_system(payload: UserIdRequest, db: Session = Depends(get_db)):
    profile = get_profile(db, payload.user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
    return agent.diagnose(profile_to_context(profile), summarize_errors(db, payload.user_id))


@router.post("/coach")
def coach_next_task(payload: SupervisorCoachRequest, db: Session = Depends(get_db)):
    profile = get_profile(db, payload.user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User profile not found.")

    historical_errors = summarize_errors(db, payload.user_id)
    result = agent.coach(
        profile=profile_to_context(profile),
        historical_errors=historical_errors,
        skill_focus=payload.skill_focus,
        learner_input=payload.learner_input,
        task_type=payload.task_type,
        speaking_part=payload.speaking_part,
    )
    selected_skill = result["supervisor_decision"]["selected_skill"]
    if not (payload.learner_input or "").strip() and selected_skill in {"reading", "listening", "writing"}:
        try:
            question = knowledge.create_question(db, payload.user_id, selected_skill, None)
            result["skill_agent_result"] = knowledge.public_question(question)
            result["manager_summary"] = "主管已从 database 资料库生成一道带书名和页码来源的训练题。"
            result["next_step"] = f"在资料库提交题目 ID {question.id} 的答案，系统会对照原资料分析。"
        except ValueError:
            pass
    _save_supervised_error(db, payload.user_id, result)
    return result


def _save_supervised_error(db: Session, user_id: int, result: dict):
    decision = result["supervisor_decision"]
    skill = decision["selected_skill"]
    skill_result = result["skill_agent_result"]

    if "saved_error" in skill_result:
        saved = skill_result["saved_error"]
        add_error(db, user_id, skill, saved["category"], saved["original_text"], saved["feedback"], saved["suggestion"])
        return

    if skill in {"reading", "listening"} and skill_result.get("correct") is False:
        feedback = skill_result.get("explanation") or skill_result.get("keyword_explanation") or "The answer needs review."
        suggestion = skill_result.get("trap") or skill_result.get("next_step") or "Review the strategy and try again."
        add_error(db, user_id, skill, "supervised_practice", "Answer submitted through supervisor.", feedback, suggestion)
