TOPIC_WORDS = {
    "education": ["curriculum", "assessment", "literacy", "discipline", "tuition", "scholarship", "seminar", "feedback"],
    "environment": ["emission", "conservation", "biodiversity", "renewable", "pollution", "habitat", "sustainable", "recycle"],
    "technology": ["innovation", "automation", "privacy", "algorithm", "device", "platform", "digital", "efficiency"],
    "society": ["community", "inequality", "welfare", "migration", "citizen", "policy", "urban", "tradition"],
    "health": ["nutrition", "prevention", "treatment", "fitness", "mental", "diagnosis", "recovery", "lifestyle"],
    "work": ["career", "employer", "productivity", "salary", "colleague", "remote", "promotion", "workload"],
    "culture": ["heritage", "identity", "custom", "festival", "language", "belief", "artistic", "diversity"],
}


class VocabularyAgent:
    def generate(self, topic: str, count: int, target_band: float) -> dict:
        words = TOPIC_WORDS.get(topic, TOPIC_WORDS["education"])[:count]
        items = []
        for idx, word in enumerate(words, start=1):
            items.append(
                {
                    "word": word,
                    "meaning": f"A useful {topic} topic word for IELTS Band {target_band}.",
                    "example_sentence": f"{word.capitalize()} is often discussed in IELTS {topic} questions.",
                    "collocation": f"{word} issue / {word} policy / improve {word}",
                    "IELTS_usage": "Use it only when it directly supports your idea; do not force advanced words.",
                    "spaced_repetition": {"mastery_level": 0, "next_review_day": idx},
                }
            )
        return {
            "topic": topic,
            "target_band": target_band,
            "items": items,
            "next_step": "Learn the words, write one original sentence for each, and review them on their next_review_day.",
        }

