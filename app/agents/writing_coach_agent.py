import re


class WritingCoachAgent:
    def review(self, essay_text: str, task_type: str | None, historical_errors: list[dict]) -> dict:
        words = re.findall(r"\b[\w'-]+\b", essay_text)
        word_count = len(words)
        detected_type = task_type or ("Task 1" if any(x in essay_text.lower() for x in ["chart", "graph", "table", "diagram"]) else "Task 2")
        long_sentences = [s.strip() for s in re.split(r"[.!?]", essay_text) if len(s.split()) > 28]
        repeated = self._find_repeated_words(words)
        estimated = self._estimate_band(word_count, long_sentences, repeated)
        sample_sentence = long_sentences[0] if long_sentences else (essay_text[:160] + "...")

        category = "sentence_control" if long_sentences else "idea_development"
        feedback = "Some sentences are too long and may reduce clarity." if long_sentences else "Ideas need more specific support and examples."
        suggestion = "Split long sentences and make the main claim visible." if long_sentences else "Add one concrete example after each main reason."

        return {
            "essay_type": detected_type,
            "word_count": word_count,
            "estimated_band_score": estimated,
            "disclaimer": "This is an estimated score from an AI learning coach, not an official IELTS examiner.",
            "criteria": {
                "Task Response / Task Achievement": self._task_feedback(detected_type, word_count),
                "Coherence and Cohesion": "Check paragraph purpose. Use linking words only when they show a real logic relationship.",
                "Lexical Resource": f"Repeated words to improve: {', '.join(repeated[:5]) or 'none obvious in this short sample'}.",
                "Grammatical Range and Accuracy": "Use a mix of simple accurate sentences and controlled complex sentences.",
            },
            "specific_problem": {
                "original_sentence": sample_sentence,
                "problem": feedback,
                "rewrite": self._rewrite_sentence(sample_sentence),
            },
            "higher_band_version": self._higher_band_version(detected_type),
            "saved_error": {
                "category": category,
                "original_text": sample_sentence,
                "feedback": feedback,
                "suggestion": suggestion,
            },
            "history_based_tip": self._history_tip(historical_errors),
            "next_step": "Rewrite the weakest paragraph, then submit only that paragraph for a second review.",
        }

    def _estimate_band(self, word_count: int, long_sentences: list[str], repeated: list[str]) -> float:
        score = 6.0
        if word_count < 180:
            score -= 0.5
        if word_count >= 250:
            score += 0.3
        if len(long_sentences) > 2:
            score -= 0.4
        if len(repeated) > 4:
            score -= 0.2
        return max(4.0, min(8.0, round(score, 1)))

    def _find_repeated_words(self, words: list[str]) -> list[str]:
        stop = {"the", "a", "an", "and", "to", "of", "in", "is", "are", "it", "that", "for", "with"}
        counts: dict[str, int] = {}
        for word in words:
            key = word.lower()
            if len(key) > 3 and key not in stop:
                counts[key] = counts.get(key, 0) + 1
        return [word for word, count in sorted(counts.items(), key=lambda x: x[1], reverse=True) if count >= 3]

    def _task_feedback(self, task_type: str, word_count: int) -> str:
        if "1" in task_type:
            return "For Task 1, describe the main trend first, then compare key data. Avoid explaining causes unless the task asks."
        if word_count < 250:
            return "For Task 2, the response is probably underdeveloped. Add clearer reasons and examples."
        return "The response attempts the task. Make sure every paragraph directly supports your position."

    def _rewrite_sentence(self, sentence: str) -> str:
        return "A clearer version: The main point should be stated first, followed by one specific example that proves it."

    def _higher_band_version(self, task_type: str) -> str:
        if "1" in task_type:
            return "Overall, the data shows a clear upward trend, although the rate of growth differs between categories."
        return "Although this policy may create short-term pressure, it can be effective if schools give students practical support."

    def _history_tip(self, historical_errors: list[dict]) -> str:
        if not historical_errors:
            return "No previous writing errors found yet. The system will become more personal after several reviews."
        categories = ", ".join({item["category"] for item in historical_errors[:5]})
        return f"Your recent notebook shows repeated issues in: {categories}. Check these before writing the next essay."

