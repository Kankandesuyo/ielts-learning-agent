class ListeningCoachAgent:
    TRANSCRIPT = (
        "Receptionist: The library tour starts at quarter past nine, not nine thirty. "
        "Please meet near the main entrance and bring your student card."
    )

    def practice(self, scenario: str | None, user_answer: str | None) -> dict:
        scene = scenario or "library"
        correct_answer = "9:15"
        if not user_answer:
            return {
                "scenario": scene,
                "transcript": self.TRANSCRIPT,
                "question": "What time does the library tour start?",
                "audio_ready": False,
                "future_audio_api": "/listening/audio can be added later for real audio input.",
                "next_step": "Answer with the start time, then submit for checking.",
            }
        normalized = user_answer.strip().replace(" ", "")
        is_correct = normalized in {"9:15", "09:15", "quarterpastnine"}
        return {
            "scenario": scene,
            "correct": is_correct,
            "correct_answer": correct_answer,
            "keyword_explanation": "The keyword is 'starts'. The trap is 'not nine thirty', so 9:30 is rejected.",
            "synonym_or_paraphrase": "quarter past nine = 9:15",
            "trap": "IELTS listening often gives a wrong option first and corrects it immediately.",
            "next_step": "Practise writing times quickly: 8:45, 9:15, 10:30, 11:05.",
        }

