import re
from pathlib import Path

from pypdf import PdfReader

from app.services.llm_service import LlmClient


class ReadingExamService:
    """Source-backed Cambridge IELTS 16 Academic Reading Test 1."""

    BOOK_PATTERN = "Cambridge-IELTS-16*.pdf"
    ANSWERS = {
        1: "FALSE", 2: "FALSE", 3: "NOT GIVEN", 4: "TRUE", 5: "TRUE", 6: "FALSE", 7: "TRUE",
        8: "violent", 9: "tool", 10: "meat", 11: "photographer", 12: "game", 13: "frustration",
        14: "iv", 15: "vii", 16: "ii", 17: "v", 18: "i", 19: "viii", 20: "vi",
        21: "city", 22: "priests", 23: "trench", 24: "location", 25: "B", 26: "D",
        27: "B", 28: "D", 29: "C", 30: "D", 31: "G", 32: "E", 33: "C", 34: "F",
        35: "B", 36: "A", 37: "C", 38: "A", 39: "B", 40: "C",
    }

    SECTION_CONFIG = [
        {
            "passage_number": 1,
            "article_title": "Why we need to protect polar bears",
            "passage_pages": [16, 17],
            "question_pages": [18, 19],
            "question_range": [1, 13],
        },
        {
            "passage_number": 2,
            "article_title": "The Step Pyramid of Djoser",
            "passage_pages": [21, 22],
            "question_pages": [20, 23],
            "question_range": [14, 26],
        },
        {
            "passage_number": 3,
            "article_title": "The future of work",
            "passage_pages": [24, 25],
            "question_pages": [26, 27, 28],
            "question_range": [27, 40],
        },
    ]

    def __init__(self, database_dir: str = "database") -> None:
        matches = sorted(Path(database_dir).glob(self.BOOK_PATTERN))
        if not matches:
            raise FileNotFoundError("Cambridge IELTS 16 PDF not found in database.")
        self.path = matches[0]

    def exam(self) -> dict:
        reader = PdfReader(str(self.path))
        sections = []
        for config in self.SECTION_CONFIG:
            passage_number = config["passage_number"]
            question_start, question_end = config["question_range"]
            raw_passage = self._pages(reader, config["passage_pages"])
            raw_questions = self._pages(reader, config["question_pages"])
            sections.append(
                {
                    # Keep these fields separate so the browser can present a
                    # real visual hierarchy instead of one long PDF text blob.
                    "passage_number": passage_number,
                    "article_title": config["article_title"],
                    "title": f"Reading Passage {passage_number} - {config['article_title']}",
                    "question_label": f"Questions {question_start}-{question_end}",
                    "recommended_minutes": 20,
                    "passage": self._strip_passage_chrome(
                        raw_passage,
                        passage_number,
                        config["article_title"],
                    ),
                    "questions": self._strip_question_chrome(raw_questions),
                    "question_numbers": list(range(question_start, question_end + 1)),
                    "source_pages": sorted(config["passage_pages"] + config["question_pages"]),
                    "question_pages": config["question_pages"],
                }
            )
        return {
            "exam_id": "cambridge16-academic-reading-test1",
            "title": "Cambridge IELTS 16 Academic - Reading Test 1",
            "module": "Academic Reading",
            "duration_minutes": 60,
            "total_questions": 40,
            "instructions": [
                "Answer all 40 questions.",
                "You have 60 minutes. There is no extra transfer time.",
                "Follow each question group's word limit exactly.",
                "Submit the whole paper once you finish.",
            ],
            "sections": sections,
            "source": {"book": self.path.name, "answer_key_page": 122},
        }

    def explain_vocabulary(self, term: str, section_index: int, area: str = "questions") -> dict:
        """Locate a selected term in authoritative PDF question or passage pages."""
        if section_index < 0 or section_index >= len(self.SECTION_CONFIG):
            raise ValueError("Invalid exam section.")
        if area not in {"questions", "passage"}:
            raise ValueError("Invalid exam text area.")

        reader = PdfReader(str(self.path))
        cleaned_term = self._clean_selected_term(term)

        # Prefer the section reported by the browser, but recover gracefully if
        # a stale DOM selection supplied the neighbouring section index.  We
        # still search only the requested authoritative PDF pages, so callers
        # cannot inject their own context into the LLM prompt.
        search_order = [section_index] + [
            index for index in range(len(self.SECTION_CONFIG)) if index != section_index
        ]
        located = None
        page_key = "question_pages" if area == "questions" else "passage_pages"
        for actual_section_index in search_order:
            candidate_config = self.SECTION_CONFIG[actual_section_index]
            candidate_text = self._pages(reader, candidate_config[page_key])
            candidate_match = self._find_selected_term(candidate_text, cleaned_term)
            if candidate_match is not None:
                located = (actual_section_index, candidate_config, candidate_text, candidate_match)
                break

        if located is None:
            raise ValueError("未在数据库试题对应区域中找到该词。请重新选中一个完整的英文单词或短语。")

        actual_section_index, config, question_text, match = located

        sentence_start = max(question_text.rfind(".", 0, match.start()) + 1, match.start() - 100)
        next_period = question_text.find(".", match.end())
        natural_end = next_period + 1 if next_period >= 0 else match.end() + 140
        sentence_end = min(len(question_text), natural_end, match.end() + 140)
        context_slice = question_text[sentence_start:sentence_end]
        if sentence_start > 0 and question_text[sentence_start - 1].isalpha():
            context_slice = context_slice.split(" ", 1)[-1]
        if sentence_end < len(question_text) and question_text[sentence_end].isalpha():
            context_slice = context_slice.rsplit(" ", 1)[0]
        context = " ".join(context_slice.split())
        explanation = LlmClient().vocabulary_explanation(cleaned_term, context)
        return {
            "term": cleaned_term,
            "context": context,
            "source": {
                "book": self.path.name,
                "pages": config[page_key],
                "section_index": actual_section_index,
                "area": area,
            },
            **explanation,
        }

    @staticmethod
    def _clean_selected_term(term: str) -> str:
        """Normalize browser/PDF punctuation without changing the words."""
        return " ".join(
            term.translate(
                str.maketrans({"\u2018": "'", "\u2019": "'", "\u2010": "-", "\u2011": "-", "\u2013": "-"})
            ).split()
        ).strip()

    @staticmethod
    def _find_selected_term(source_text: str, term: str) -> re.Match[str] | None:
        """Match a selected word/phrase despite harmless PDF typography differences."""
        tokens = re.split(r"([ '-]+)", term)
        pattern_parts = []
        for token in tokens:
            if not token:
                continue
            if token.isspace():
                pattern_parts.append(r"\s+")
            elif set(token) <= {"'", " "}:
                pattern_parts.append(r"['\u2018\u2019]\s*")
            elif set(token) <= {"-", " "}:
                pattern_parts.append(r"(?:[-\u2010\u2011\u2013]\s*|\s+)")
            else:
                pattern_parts.append(re.escape(token))
        pattern = "".join(pattern_parts)
        return re.search(rf"(?i)(?<![A-Za-z]){pattern}(?![A-Za-z])", source_text)

    def grade(self, answers: dict[str, str]) -> dict:
        details = []
        correct_count = 0
        pair_answers = {self._normalize(answers.get("25", "")), self._normalize(answers.get("26", ""))}
        pair_correct = pair_answers == {"B", "D"}

        for number, expected in self.ANSWERS.items():
            given = answers.get(str(number), "").strip()
            if number in {25, 26}:
                correct = pair_correct
            else:
                correct = self._normalize(given) == self._normalize(expected)
            correct_count += int(correct)
            details.append(
                {
                    "number": number,
                    "your_answer": given or "(blank)",
                    "correct_answer": "B / D in either order" if number in {25, 26} else expected,
                    "correct": correct,
                    "source": {"book": self.path.name, "answer_key_page": 122},
                }
            )

        return {
            "exam_id": "cambridge16-academic-reading-test1",
            "raw_score": correct_count,
            "total": 40,
            "estimated_band": self._band(correct_count),
            "details": details,
            "analysis": self._analysis(details),
            "disclaimer": "Band is an estimated Academic Reading conversion for learning use, not an official IELTS result.",
            "source": {"book": self.path.name, "answer_key_page": 122},
        }

    @staticmethod
    def _pages(reader: PdfReader, pages: list[int]) -> str:
        return "\n\n".join(" ".join((reader.pages[page - 1].extract_text() or "").split()) for page in pages)

    @staticmethod
    def _strip_passage_chrome(text: str, passage_number: int, article_title: str) -> str:
        """Remove repeated PDF page furniture while preserving the source article.

        Cambridge pages print the test name, passage number, timing guidance,
        and article title directly before the body. Those are useful pieces of
        information, but the frontend renders them as separate headings.
        """
        cleaned = re.sub(
            r"^Test\s+\d+\s+(?:ACADEMIC\s+)?READING\s+",
            "",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"^(?:READING\s+)?PASSAGE\s+{passage_number}\s+"
            rf"You should spend about 20 minutes on Questions \d+[-\u2013]\d+,\s+"
            rf"which are based on Reading Passage {passage_number} "
            rf"(?:below|on pages? \d+(?: and \d+)?)\.\s*",
            "",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"^Reading\s+", "", cleaned, count=1, flags=re.IGNORECASE)

        # PDF extraction occasionally joins words in a heading (for example
        # "ofDjoser"). Matching optional whitespace removes only the known,
        # anchored article title and not any body copy.
        title_pattern = r"\s*".join(re.escape(word) for word in article_title.split())
        cleaned = re.sub(rf"^{title_pattern}\s*", "", cleaned, count=1, flags=re.IGNORECASE)
        # Remove page-turn furniture such as "16 Reading" and "21 Test 1"
        # that otherwise appears as if it were part of the article.
        cleaned = re.sub(
            r"\s+\d{1,3}\s+(?:Reading|Test\s+\d+)\s+",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+\d{1,3}\s*$", "", cleaned)
        return cleaned.strip()

    @staticmethod
    def _strip_question_chrome(text: str) -> str:
        """Remove PDF page labels without touching actual question numbers."""
        cleaned = re.sub(r"^Test\s+\d+\s+", "", text, count=1, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"^(?:READING\s+)?PASSAGE\s+\d+\s+"
            r"You should spend about \d+ minutes on Questions\s+\d+\s*[-\u2013]\s*\d+,\s+"
            r"which are based on Reading Passage\s+\d+\s+"
            r"(?:below|on pages?\s+\d+(?:\s+and\s+\d+)?)\.\s*",
            "",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\s+\d{1,3}\s+Test\s+\d+\s+(?=Questions\s+\d)",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\s+\d{1,3}\s+(?=(?:Test\s+\d+\s+)?Questions\s+\d)",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+Reading\s+(?=Questions\s+\d)", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+\d{1,3}\s+\S{1,8}\s+p\.\s+\d+\s+(?=List\b)", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+\S{1,8}\s+p\.\s+\d+\s+\d{1,3}\s*$", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    @staticmethod
    def _normalize(value: str) -> str:
        value = re.sub(r"\s+", " ", value.strip().upper())
        return value.replace("NOTGIVEN", "NOT GIVEN")

    @staticmethod
    def _band(score: int) -> float:
        thresholds = [(39, 9.0), (37, 8.5), (35, 8.0), (33, 7.5), (30, 7.0), (27, 6.5), (23, 6.0), (19, 5.5), (15, 5.0), (13, 4.5), (10, 4.0)]
        return next((band for minimum, band in thresholds if score >= minimum), 3.5)

    @staticmethod
    def _analysis(details: list[dict]) -> dict:
        groups = {
            "Passage 1 (1-13)": details[:13],
            "Passage 2 (14-26)": details[13:26],
            "Passage 3 (27-40)": details[26:40],
        }
        scores = {name: sum(item["correct"] for item in items) for name, items in groups.items()}
        weakest = min(scores, key=scores.get)
        return {
            "section_scores": scores,
            "weakest_section": weakest,
            "next_step": f"优先复盘 {weakest} 的错题，回到文章定位原句并记录同义替换。",
        }
