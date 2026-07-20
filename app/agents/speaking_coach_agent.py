class SpeakingCoachAgent:
    QUESTIONS = {
        1: ["Do you work or study?", "What do you usually do after class?", "Do you prefer studying alone or with others?"],
        2: ["Describe a skill you want to improve. You should say what it is, why you want to improve it, and how you plan to do it."],
        3: ["Why do some people stop learning new skills?", "How can schools help students become independent learners?"],
    }

    def practice(self, part: int, answer_text: str | None, topic: str | None, historical_errors: list[dict]) -> dict:
        question = self.QUESTIONS.get(part, self.QUESTIONS[1])[0]
        if topic:
            question = f"{question} Try to connect your answer with: {topic}."
        if not answer_text:
            return {
                "part": part,
                "question": question,
                "examiner_follow_up": "Can you give me a specific example?",
                "next_step": "Answer in 4-6 sentences, then send your answer for feedback.",
            }

        word_count = len(answer_text.split())
        filler_flags = [x for x in ["very very", "I think I think", "you know"] if x.lower() in answer_text.lower()]
        estimated = 5.5 + (0.4 if word_count >= 45 else 0) - (0.3 if filler_flags else 0)
        saved = {
            "category": "fluency" if filler_flags else "specificity",
            "original_text": answer_text[:180],
            "feedback": "Avoid repeated fillers." if filler_flags else "The answer needs one more concrete personal example.",
            "suggestion": "Pause briefly instead of repeating fillers." if filler_flags else "Add a time, place, or result to make the answer more convincing.",
        }
        return {
            "part": part,
            "question": question,
            "estimated_band_score": round(max(4.0, min(8.0, estimated)), 1),
            "disclaimer": "Pronunciation feedback is limited because this MVP only receives text, not audio.",
            "feedback": {
                "Fluency and Coherence": saved["feedback"],
                "Lexical Resource": "Use topic-specific words, but keep them natural.",
                "Grammatical Range and Accuracy": "Try one accurate complex sentence with because, although, or which.",
                "Pronunciation": "Text-only review cannot judge sounds, stress, or intonation.",
            },
            "more_natural_expression": "Instead of giving a memorized answer, start with a direct answer, add one real detail, then explain why it matters.",
            "sample_answer": "I would like to improve my academic writing because it affects both my IELTS score and my university study. At the moment, I can explain simple ideas, but I sometimes struggle to organize examples clearly. I plan to practise one paragraph every day and review my repeated grammar mistakes each weekend.",
            "examiner_follow_up": "What makes this skill difficult for you?",
            "saved_error": saved,
            "history_based_tip": "Review your previous speaking notebook before practising." if historical_errors else "No previous speaking errors found yet.",
            "next_step": "Record yourself reading the improved answer and check whether it sounds natural, not memorized.",
        }

