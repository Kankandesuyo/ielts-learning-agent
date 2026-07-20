from collections import Counter
from typing import Any

from app.agents.listening_coach_agent import ListeningCoachAgent
from app.agents.reading_coach_agent import ReadingCoachAgent
from app.agents.speaking_coach_agent import SpeakingCoachAgent
from app.agents.writing_coach_agent import WritingCoachAgent
from app.services.llm_service import LlmClient


class SupervisorAgent:
    """Coordinate the four IELTS skill agents.

    Product view:
    - The supervisor decides what the learner should do next.
    - Skill agents only handle their own training task.
    - The API can expose both direct practice and guided practice.
    """

    SUPPORTED_SKILLS = {"listening", "speaking", "reading", "writing"}

    def __init__(self) -> None:
        self.listening_agent = ListeningCoachAgent()
        self.speaking_agent = SpeakingCoachAgent()
        self.reading_agent = ReadingCoachAgent()
        self.writing_agent = WritingCoachAgent()
        self.llm = LlmClient()

    def diagnose(self, profile: dict[str, Any], historical_errors: list[dict]) -> dict[str, Any]:
        priority = self._choose_priority(profile, historical_errors, None)
        reason = self._priority_reason(priority, profile, historical_errors)
        return {
            "product_concept": "A main IELTS supervisor agent routes the learner to four specialist agents: listening, speaking, reading, and writing.",
            "supervisor_role": [
                "Read the learner profile.",
                "Check weak skills and recent notebook errors.",
                "Choose the next best training module.",
                "Return one clear next step instead of many scattered suggestions.",
            ],
            "agent_team": {
                "listening_agent": "Trains transcript listening, keyword capture, time and number traps.",
                "speaking_agent": "Gives speaking questions, follow-up prompts, and text-based fluency feedback.",
                "reading_agent": "Trains locating words, synonyms, and True/False/Not Given traps.",
                "writing_agent": "Reviews Task 1/Task 2 essays using IELTS-style criteria.",
            },
            "current_learning_priority": priority,
            "reason": reason,
            "llm_manager_note": self.llm.supervisor_note(profile, priority, reason),
            "security_measures": [
                "Pydantic request models validate IDs, text length, and allowed skill names.",
                "Routers check that the user profile exists before running any agent.",
                "The system stores only learning errors, not passwords or payment data.",
                "Scores are labelled as estimated learning feedback, not official IELTS results.",
                "Future production work should add login, rate limiting, HTTPS, and log masking.",
            ],
            "next_step": f"Run /supervisor/coach with skill_focus='{priority}' or leave skill_focus empty and let the supervisor route automatically.",
        }

    def coach(
        self,
        profile: dict[str, Any],
        historical_errors: list[dict],
        skill_focus: str | None,
        learner_input: str | None,
        task_type: str | None,
        speaking_part: int,
    ) -> dict[str, Any]:
        skill = self._choose_priority(profile, historical_errors, skill_focus)
        reason = self._priority_reason(skill, profile, historical_errors)
        result = self._run_skill_agent(skill, learner_input, task_type, speaking_part, historical_errors)
        return {
            "supervisor_decision": {
                "selected_agent": f"{skill}_agent",
                "selected_skill": skill,
                "reason": reason,
            },
            "skill_agent_result": result,
            "manager_summary": self._manager_summary(skill, result),
            "llm_manager_note": self.llm.supervisor_note(profile, skill, reason),
            "next_step": self._next_step(skill, result),
        }

    def _choose_priority(self, profile: dict[str, Any], historical_errors: list[dict], skill_focus: str | None) -> str:
        normalized_focus = (skill_focus or "").strip().lower()
        if normalized_focus in self.SUPPORTED_SKILLS:
            return normalized_focus

        weak_skills = [item.lower() for item in profile.get("weak_skills", [])]
        for skill in ("writing", "speaking", "reading", "listening"):
            if skill in weak_skills:
                return skill

        if historical_errors:
            counts = Counter(item["source"] for item in historical_errors if item.get("source") in self.SUPPORTED_SKILLS)
            if counts:
                return counts.most_common(1)[0][0]

        return "writing"

    def _run_skill_agent(
        self,
        skill: str,
        learner_input: str | None,
        task_type: str | None,
        speaking_part: int,
        historical_errors: list[dict],
    ) -> dict[str, Any]:
        text = (learner_input or "").strip()
        if skill == "writing":
            essay = text or "Online learning is useful because students can study anywhere, but they still need teacher feedback."
            return self.writing_agent.review(essay, task_type or "Task 2", historical_errors)
        if skill == "speaking":
            return self.speaking_agent.practice(speaking_part, text or None, None, historical_errors)
        if skill == "reading":
            return self.reading_agent.practice(None, text or None)
        return self.listening_agent.practice(None, text or None)

    def _priority_reason(self, skill: str, profile: dict[str, Any], historical_errors: list[dict]) -> str:
        weak_skills = [item.lower() for item in profile.get("weak_skills", [])]
        if skill in weak_skills:
            return f"{skill} is listed as a weak skill in the learner profile."
        if any(item.get("source") == skill for item in historical_errors):
            return f"Recent notebook errors include {skill}, so the supervisor routes practice there."
        return "No stronger signal was found, so writing is used as the default high-impact IELTS skill."

    def _manager_summary(self, skill: str, result: dict[str, Any]) -> str:
        if "estimated_band_score" in result:
            return f"The {skill} agent returned an estimated band of {result['estimated_band_score']} and one concrete next step."
        if "question" in result:
            return f"The {skill} agent prepared a practice question. The learner should answer it before moving on."
        return f"The {skill} agent completed the task and returned feedback."

    def _next_step(self, skill: str, result: dict[str, Any]) -> str:
        if result.get("next_step"):
            return result["next_step"]
        return f"Complete one more {skill} task and save any mistakes to the notebook."
