import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudyPlan, StudyPlanDay


def save_plan(db: Session, user_id: int, result: dict) -> StudyPlan:
    plan = StudyPlan(
        user_id=user_id,
        days=len(result["plan"]),
        estimated_goal_gap=result["estimated_goal_gap"],
    )
    db.add(plan)
    db.flush()
    for day in result["plan"]:
        db.add(
            StudyPlanDay(
                plan_id=plan.id,
                day_number=day["day"],
                task_json=json.dumps(day, ensure_ascii=False),
            )
        )
    db.commit()
    db.refresh(plan)
    return plan


def get_latest_plan(db: Session, user_id: int) -> StudyPlan | None:
    stmt = select(StudyPlan).where(StudyPlan.user_id == user_id).order_by(StudyPlan.created_at.desc(), StudyPlan.id.desc())
    return db.scalar(stmt)


def get_plan(db: Session, user_id: int, plan_id: int) -> StudyPlan | None:
    stmt = select(StudyPlan).where(StudyPlan.id == plan_id, StudyPlan.user_id == user_id)
    return db.scalar(stmt)


def get_plan_day(db: Session, plan_id: int, day_number: int) -> StudyPlanDay | None:
    stmt = select(StudyPlanDay).where(StudyPlanDay.plan_id == plan_id, StudyPlanDay.day_number == day_number)
    return db.scalar(stmt)


def set_day_status(db: Session, day: StudyPlanDay, completed: bool) -> None:
    day.completed = completed
    day.completed_at = datetime.now(timezone.utc) if completed else None
    db.commit()


def plan_to_dict(db: Session, plan: StudyPlan) -> dict:
    days = list(db.scalars(select(StudyPlanDay).where(StudyPlanDay.plan_id == plan.id).order_by(StudyPlanDay.day_number)))
    completed_days = sum(1 for day in days if day.completed)
    tasks = []
    for day in days:
        task = json.loads(day.task_json)
        task["completed"] = day.completed
        task["completed_at"] = day.completed_at.isoformat() if day.completed_at else None
        tasks.append(task)
    return {
        "plan_id": plan.id,
        "user_id": plan.user_id,
        "days": plan.days,
        "completed_days": completed_days,
        "progress_percent": round(completed_days / plan.days * 100) if plan.days else 0,
        "estimated_goal_gap": plan.estimated_goal_gap,
        "created_at": plan.created_at.isoformat(),
        "plan": tasks,
    }
