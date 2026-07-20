from app.agents.base import make_graph_runner, split_minutes


class StudyPlanAgent:
    def __init__(self) -> None:
        self.run = make_graph_runner(self._generate)

    def generate(self, profile: dict, days: int | None = None) -> dict:
        payload = {**profile, "days": days or min(profile["prep_days"], 7)}
        return self.run(payload)

    def _generate(self, payload: dict) -> dict:
        days = min(payload["days"], payload["prep_days"])
        minutes = split_minutes(payload["daily_minutes"], payload["weak_skills"])
        weak = ", ".join(payload["weak_skills"]) or "balanced skills"
        focus = ", ".join(payload["focus_areas"]) or "core IELTS skills"

        plan = []
        for day in range(1, days + 1):
            is_review_day = day % 7 == 0
            plan.append(
                {
                    "day": day,
                    "listening": f"{minutes['listening']} min: text-based Section {1 + day % 4} practice; underline keywords and synonym replacements.",
                    "reading": f"{minutes['reading']} min: one passage drill; mark locating words before answering.",
                    "writing": f"{minutes['writing']} min: write one paragraph or outline; check logic, grammar, and topic vocabulary.",
                    "speaking": f"{minutes['speaking']} min: answer 3 questions aloud, then rewrite one answer naturally.",
                    "vocabulary": f"{minutes['vocabulary']} min: learn 8 topic words about {focus}; review old weak words.",
                    "review": "Weekly mock test and error notebook review." if is_review_day else f"Record 2 mistakes related to {weak}.",
                }
            )

        return {
            "estimated_goal_gap": round(payload["target_band"] - payload["current_band"], 1),
            "time_allocation_minutes": minutes,
            "mock_test_plan": "Do a short mock every 7 days; do a full mock in the final 10 days.",
            "weakness_plan": f"Give extra drills to: {weak}.",
            "plan": plan,
            "next_step": "Start Day 1 and save every mistake into the error notebook.",
        }

