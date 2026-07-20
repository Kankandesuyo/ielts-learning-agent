import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import KnowledgeQuestion


STOP_WORDS = {
    "about", "after", "again", "also", "another", "because", "before", "between", "could", "first",
    "from", "have", "into", "more", "most", "other", "over", "people", "should", "some", "than", "that",
    "their", "there", "these", "they", "this", "those", "through", "under", "very", "which", "while", "with",
    "would", "your", "question", "answer", "cambridge", "ielts", "academic", "information",
}


class KnowledgeService:
    """Build a local, source-traceable index from the user's database folder."""

    def __init__(self) -> None:
        settings = get_settings()
        self.source_dir = settings.knowledge_path
        self.index_file = settings.knowledge_index_file
        self._index: dict | None = None

    def status(self) -> dict:
        source_files = self._source_files()
        index = self._load_index_if_fresh(source_files)
        return {
            "source_directory": str(self.source_dir),
            "supported_files": len(source_files),
            "unsupported_files": [p.name for p in self.source_dir.glob("*") if p.is_file() and p.suffix.lower() not in {".pdf", ".txt", ".md"}],
            "indexed": index is not None,
            "indexed_pages": len(index.get("chunks", [])) if index else 0,
            "sources": [p.name for p in source_files],
        }

    def build_index(self, force: bool = False) -> dict:
        files = self._source_files()
        if not force:
            cached = self._load_index_if_fresh(files)
            if cached is not None:
                self._index = cached
                return self._summary(cached, rebuilt=False)

        chunks: list[dict] = []
        errors: list[dict] = []
        for path in files:
            try:
                if path.suffix.lower() == ".pdf":
                    reader = PdfReader(str(path))
                    for page_number, page in enumerate(reader.pages, start=1):
                        text = self._clean_text(page.extract_text() or "")
                        if len(text) >= 100:
                            chunks.extend(self._page_chunks(path.name, page_number, text))
                else:
                    text = self._clean_text(path.read_text(encoding="utf-8", errors="ignore"))
                    chunks.extend(self._page_chunks(path.name, 1, text))
            except Exception as exc:
                errors.append({"source": path.name, "error": str(exc)})

        index = {"fingerprint": self._fingerprint(files), "chunks": chunks, "errors": errors}
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        self.index_file.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        self._index = index
        return self._summary(index, rebuilt=True)

    def retrieve(self, query: str, top_k: int = 5, skill: str | None = None) -> list[dict]:
        index = self._ensure_index()
        query_tokens = self._tokens(query)
        scored = []
        for chunk in index["chunks"]:
            text_lower = chunk["text"].lower()
            overlap = sum(1 for token in query_tokens if token in text_lower)
            section_bonus = self._skill_bonus(skill, text_lower)
            score = overlap * 3 + section_bonus
            if score > 0:
                scored.append({**chunk, "score": score})
        scored.sort(key=lambda item: (item["score"], len(item["text"])), reverse=True)
        return scored[:top_k]

    def create_question(self, db: Session, user_id: int, skill: str, topic: str | None) -> KnowledgeQuestion:
        query = f"{skill} {topic or ''}".strip()
        candidates = self.retrieve(query, top_k=30, skill=skill)
        candidates = self._skill_candidates(candidates, skill)
        if not candidates:
            raise ValueError("资料索引中没有找到可用于出题的内容。")
        # Rotate source candidates per learner so an automatically prepared
        # next question does not repeat the same top-ranked passage forever.
        answered_count = db.query(KnowledgeQuestion).filter(KnowledgeQuestion.user_id == user_id).count()
        offset = answered_count % len(candidates)
        candidates = candidates[offset:] + candidates[:offset]

        if skill == "writing":
            chunk = self._best_writing_chunk(candidates)
            prompt = self._writing_prompt(chunk["text"])
            question_type = "writing_prompt"
            answer = ""
            explanation = "将按 Task Response、Coherence and Cohesion、Lexical Resource、Grammar 四项分析。"
            passage = ""
        else:
            chunk, sentence, answer = self._cloze_candidate(candidates)
            question_type = "source_cloze"
            prompt = sentence.replace(answer, "_____", 1)
            passage = self._context_without_answer(chunk["text"], sentence, answer)
            explanation = f"原资料中的完整表达是：{sentence}"

        item = KnowledgeQuestion(
            user_id=user_id,
            skill=skill,
            question_type=question_type,
            question=prompt,
            passage=passage,
            correct_answer=answer,
            explanation=explanation,
            source=chunk["source"],
            page=chunk["page"],
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def get_question(db: Session, question_id: int, user_id: int) -> KnowledgeQuestion | None:
        return db.query(KnowledgeQuestion).filter(
            KnowledgeQuestion.id == question_id, KnowledgeQuestion.user_id == user_id
        ).first()

    @staticmethod
    def public_question(item: KnowledgeQuestion) -> dict:
        return {
            "question_id": item.id,
            "skill": item.skill,
            "question_type": item.question_type,
            "passage": KnowledgeService._clean_source_excerpt(item.passage),
            "question": item.question,
            "source": {"book": item.source, "page": item.page},
            "next_step": "提交答案后，系统会结合原资料给出分析。",
        }

    def _ensure_index(self) -> dict:
        files = self._source_files()
        if self._index is not None and self._index.get("fingerprint") == self._fingerprint(files):
            return self._index
        cached = self._load_index_if_fresh(files)
        if cached is None:
            self.build_index(force=True)
        else:
            self._index = cached
        return self._index or {"chunks": []}

    def _source_files(self) -> list[Path]:
        if not self.source_dir.exists():
            return []
        return sorted((p for p in self.source_dir.iterdir() if p.suffix.lower() in {".pdf", ".txt", ".md"}), key=lambda p: p.name)

    @staticmethod
    def _fingerprint(files: list[Path]) -> list[dict]:
        return [{"name": p.name, "size": p.stat().st_size, "mtime": p.stat().st_mtime_ns} for p in files]

    def _load_index_if_fresh(self, files: list[Path]) -> dict | None:
        if not self.index_file.exists():
            return None
        try:
            data = json.loads(self.index_file.read_text(encoding="utf-8"))
            return data if data.get("fingerprint") == self._fingerprint(files) else None
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _page_chunks(source: str, page: int, text: str, size: int = 1600, overlap: int = 200) -> list[dict]:
        return [
            {"source": source, "page": page, "text": text[start:start + size]}
            for start in range(0, len(text), size - overlap)
            if len(text[start:start + size]) >= 100
        ]

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {word.lower() for word in re.findall(r"[A-Za-z]{4,}", text) if word.lower() not in STOP_WORDS}

    @staticmethod
    def _skill_bonus(skill: str | None, text: str) -> int:
        markers = {
            "reading": ("reading passage", "questions 1", "true false not given"),
            "listening": ("audioscript", "section 1", "questions 1"),
            "writing": ("writing task", "write about", "summarise the information", "give reasons for your answer"),
            "vocabulary": ("dictionary", "words and phrases", "vocabulary"),
        }
        return sum(5 for marker in markers.get(skill or "", ()) if marker in text)

    @staticmethod
    def _best_writing_chunk(candidates: list[dict]) -> dict:
        markers = ("write about the following topic", "give reasons for your answer", "summarise the information", "writing task")
        return max(candidates, key=lambda item: sum(marker in item["text"].lower() for marker in markers))

    @staticmethod
    def _writing_prompt(text: str) -> str:
        lower = text.lower()
        starts = [lower.find(marker) for marker in ("write about the following topic", "the graph", "the chart", "the diagram")]
        starts = [value for value in starts if value >= 0]
        start = min(starts) if starts else 0
        prompt = text[start:start + 900]
        end_match = re.search(r"Write at least (?:150|250) words\.", prompt, flags=re.IGNORECASE)
        if end_match:
            prompt = prompt[:end_match.end()]
        return prompt.strip()

    def _cloze_candidate(self, candidates: list[dict]) -> tuple[dict, str, str]:
        for chunk in candidates:
            sentences = re.split(r"(?<=[.!?])\s+", chunk["text"])
            for sentence in sentences:
                sentence = re.sub(r"^(?:[A-Z][A-Z'.-]{1,15}:\s*){2,}", "", sentence).strip()
                lower = sentence.lower()
                if any(marker in lower for marker in ("you should spend", "questions 1", "write the correct", "answer sheet", "choose the correct")):
                    continue
                words = [w for w in re.findall(r"\b[A-Za-z]{6,}\b", sentence) if w.lower() not in STOP_WORDS]
                if 60 <= len(sentence) <= 260 and words:
                    counts = Counter(word.lower() for word in words)
                    answer = max(words, key=lambda word: (len(word), -counts[word.lower()]))
                    return chunk, sentence, answer
        raise ValueError("找到资料，但暂时无法从提取文本中生成稳定题目。")

    @staticmethod
    def _skill_candidates(candidates: list[dict], skill: str) -> list[dict]:
        if skill == "reading":
            filtered = [item for item in candidates if "reading passage" in item["text"].lower()]
            return filtered or candidates
        if skill == "listening":
            filtered = [
                item for item in candidates
                if "audioscript" in item["text"].lower()
                or len(re.findall(r"\b[A-Z]{2,15}:", item["text"])) >= 2
            ]
            return filtered or candidates
        if skill == "vocabulary":
            filtered = [item for item in candidates if "dictionary" in item["source"].lower()]
            return filtered or candidates
        return candidates

    @staticmethod
    def _context_without_answer(text: str, sentence: str, answer: str) -> str:
        cleaned = KnowledgeService._clean_source_excerpt(text)
        sentence_start = cleaned.find(sentence)
        if sentence_start < 0:
            return "请根据题干和上下文填写原文词汇。"

        # Use nearby source copy instead of the beginning of the PDF chunk.
        # This prevents publisher metadata and a preceding page header from
        # becoming more prominent than the actual exercise sentence.
        prefix = cleaned[:sentence_start].strip()
        start = 0 if len(prefix) <= 120 else max(0, sentence_start - 240)
        context = cleaned[start:sentence_start + len(sentence) + 320].strip()
        return context.replace(answer, "_____", 1)

    @staticmethod
    def _clean_source_excerpt(text: str) -> str:
        """Remove common IELTS PDF furniture from learner-facing excerpts.

        The rule is deliberately independent of a specific Cambridge book or
        test number, so newly indexed Test 2/3/4 material receives the same
        presentation cleanup.
        """
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        cleaned = re.sub(
            r"^.*?Test\s+\d+\s+(?:ACADEMIC\s+)?READING\s+"
            r"(?:READING\s+)?PASSAGE\s+\d+\s+"
            r"You should spend about \d+ minutes on Questions\s+\d+\s*[-\u2013]\s*\d+,\s+"
            r"which are based on Reading Passage\s+\d+\s+"
            r"(?:below|on pages?\s+\d+(?:\s+and\s+\d+)?)\.\s*",
            "",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\s+\d{1,3}\s+(?:Reading|Test\s+\d+)\s+",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned.strip()

    @staticmethod
    def _summary(index: dict, rebuilt: bool) -> dict:
        sources = sorted({chunk["source"] for chunk in index.get("chunks", [])})
        return {
            "rebuilt": rebuilt,
            "indexed_sources": len(sources),
            "indexed_pages": len(index.get("chunks", [])),
            "sources": sources,
            "errors": index.get("errors", []),
        }
