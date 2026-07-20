from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.study_plan_agent import StudyPlanAgent
from app.database import get_db
from app.schemas.requests import PlanDayStatusRequest, StudyPlanRequest
from app.services.profile_service import get_profile, profile_to_context
from app.services.study_plan_service import get_latest_plan, get_plan, get_plan_day, plan_to_dict, save_plan, set_day_status

router = APIRouter(prefix="/study-plan", tags=["study-plan"])
agent = StudyPlanAgent()


@router.post("/generate")
def generate_study_plan(payload: StudyPlanRequest, db: Session = Depends(get_db)):
    profile = get_profile(db, payload.user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
    result = agent.generate(profile_to_context(profile), payload.days)
    plan = save_plan(db, payload.user_id, result)
    saved = plan_to_dict(db, plan)
    saved.update({key: value for key, value in result.items() if key not in {"plan", "estimated_goal_gap"}})
    return saved


@router.get("/{user_id}/latest")
def read_latest_study_plan(user_id: int, db: Session = Depends(get_db)):
    if get_profile(db, user_id) is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
    plan = get_latest_plan(db, user_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Study plan not found.")
    return plan_to_dict(db, plan)


@router.patch("/{user_id}/{plan_id}/days/{day_number}")
def update_study_plan_day(
    user_id: int,
    plan_id: int,
    day_number: int,
    payload: PlanDayStatusRequest,
    db: Session = Depends(get_db),
):
    plan = get_plan(db, user_id, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Study plan not found.")
    day = get_plan_day(db, plan.id, day_number)
    if day is None:
        raise HTTPException(status_code=404, detail="Study plan day not found.")
    set_day_status(db, day, payload.completed)
    return plan_to_dict(db, plan)
