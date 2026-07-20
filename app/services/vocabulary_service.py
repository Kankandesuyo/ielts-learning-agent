from sqlalchemy.orm import Session

from app.models import VocabularyItem


def save_vocabulary_items(db: Session, user_id: int, topic: str, items: list[dict]) -> None:
    for item in items:
        db.add(
            VocabularyItem(
                user_id=user_id,
                topic=topic,
                word=item["word"],
                meaning=item["meaning"],
                example_sentence=item["example_sentence"],
                collocation=item["collocation"],
                ielts_usage=item["IELTS_usage"],
                mastery_level=item["spaced_repetition"]["mastery_level"],
                next_review_day=item["spaced_repetition"]["next_review_day"],
            )
        )
    db.commit()

