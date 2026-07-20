class ReadingCoachAgent:
    PASSAGE = (
        "Many universities now offer flexible online courses. Supporters argue that these courses make education "
        "more accessible, especially for students who work part-time. However, critics say that online learning "
        "requires strong self-discipline and may reduce face-to-face discussion."
    )

    def practice(self, question_type: str | None, user_answer: str | None) -> dict:
        qtype = question_type or "True / False / Not Given"
        correct_answer = "True"
        if not user_answer:
            return {
                "passage": self.PASSAGE,
                "question_type": qtype,
                "question": "Online courses can help students who have part-time jobs access education.",
                "strategy": "Locate synonyms: offer flexible online courses = help access education; students who work part-time = part-time jobs.",
                "next_step": "Choose True, False, or Not Given and send your answer.",
            }
        is_correct = user_answer.strip().lower() == correct_answer.lower()
        return {
            "question_type": qtype,
            "correct": is_correct,
            "correct_answer": correct_answer,
            "explanation": "The answer is True because the passage says online courses make education more accessible, especially for students who work part-time.",
            "locating_words": ["online courses", "accessible", "students who work part-time"],
            "synonym_replacements": [{"question": "part-time jobs", "passage": "work part-time"}],
            "trap": "Do not choose Not Given just because the wording is different. IELTS often uses synonyms.",
            "next_step": "Write down the synonym pair and try one more True/False/Not Given question.",
        }

