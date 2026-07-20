"""Read the open dictionaries stored in ``database/legal-dictionaries``.

The service deliberately uses only Python's standard library.  FreeDict is a
StarDict dictionary: its compressed index stores ``word -> byte offset/size``
records, so a lookup does not need to load the 8 MB dictionary body into RAM.
GCIDE is used as an English-definition fallback when FreeDict has no entry.
"""

from __future__ import annotations

import gzip
import html
import re
import struct
from functools import lru_cache
from pathlib import Path


class LocalDictionaryService:
    FREEDICT_GLOB = "freedict-*-stardict/eng-zho"
    GCIDE_GLOB = "gcide-*-english-english/gcide-*"

    def __init__(self, root: Path | str = "database/legal-dictionaries") -> None:
        self.root = Path(root)
        self.freedict_dir = next(iter(sorted(self.root.glob(self.FREEDICT_GLOB))), None)
        self.gcide_dir = next(iter(sorted(self.root.glob(self.GCIDE_GLOB))), None)

    def lookup(self, term: str, context: str) -> dict[str, str] | None:
        """Return a UI-ready local explanation, including simple inflections."""
        cleaned = " ".join(term.strip().lower().split())
        if not cleaned or len(cleaned) > 80:
            return None

        for candidate in self._word_candidates(cleaned):
            result = self._lookup_freedict(candidate)
            if result:
                return self._format_result(term, candidate, context, result, "freedict")

        # GCIDE is most useful for a single English word.  Multi-word scans of
        # its source files would be slow and rarely improve the learner result.
        if re.fullmatch(r"[a-z]+(?:['-][a-z]+)*", cleaned):
            for candidate in self._word_candidates(cleaned):
                result = self._lookup_gcide(candidate)
                if result:
                    return self._format_result(term, candidate, context, result, "gcide")
        return None

    def _lookup_freedict(self, word: str) -> dict[str, str] | None:
        if not self.freedict_dir:
            return None
        index = self._load_stardict_index(str(self.freedict_dir / "eng-zho.idx.gz"))
        position = index.get(word.casefold())
        if not position:
            return None
        offset, size = position
        with (self.freedict_dir / "eng-zho.dict").open("rb") as dictionary:
            dictionary.seek(offset)
            raw = dictionary.read(size).decode("utf-8", errors="replace")
        return self._parse_freedict_html(raw)

    @staticmethod
    @lru_cache(maxsize=2)
    def _load_stardict_index(index_path: str) -> dict[str, tuple[int, int]]:
        raw = gzip.open(index_path, "rb").read()
        entries: dict[str, tuple[int, int]] = {}
        cursor = 0
        while cursor < len(raw):
            word_end = raw.index(b"\0", cursor)
            word = raw[cursor:word_end].decode("utf-8", errors="replace").casefold()
            offset, size = struct.unpack(">II", raw[word_end + 1 : word_end + 9])
            entries.setdefault(word, (offset, size))
            cursor = word_end + 9
        return entries

    @classmethod
    def _parse_freedict_html(cls, raw: str) -> dict[str, str]:
        pos_match = re.search(r'class="grammar"[^>]*>([^<]+)', raw, flags=re.IGNORECASE)
        part_of_speech = html.unescape(pos_match.group(1)).strip() if pos_match else "word"

        # The FreeDict export places translations in their own <div>.  Keep a
        # few unique Chinese translations instead of returning every sense.
        div_texts = [cls._plain_text(value) for value in re.findall(r"<div[^>]*>(.*?)</div>", raw, re.I | re.S)]
        translations: list[str] = []
        for value in div_texts:
            if re.search(r"[\u3400-\u9fff]", value) and value not in translations:
                translations.append(value)

        without_pronunciation = re.sub(r"^.*?<font class=\"grammar\"[^>]*>.*?</font>", "", raw, count=1, flags=re.I | re.S)
        english_text = cls._plain_text(without_pronunciation)
        english_text = re.sub(r"[\u3400-\u9fff]+", "", english_text)
        english_text = re.sub(r"\s+", " ", english_text).strip(" ;,/\n")
        if len(english_text) > 420:
            english_text = english_text[:417].rsplit(" ", 1)[0] + "..."

        return {
            "part_of_speech": part_of_speech,
            "meaning_zh": "；".join(translations[:4]) or "本地词条暂未包含中文释义。",
            "simple_english": english_text or "See the selected word in its sentence.",
        }

    def _lookup_gcide(self, word: str) -> dict[str, str] | None:
        if not self.gcide_dir or not word[0].isalpha():
            return None
        source = self.gcide_dir / f"CIDE.{word[0].upper()}"
        if not source.exists():
            return None
        text = self._read_text(str(source))
        entry_start = re.search(rf"(?is)<p><ent>{re.escape(word)}</ent><br/", text)
        if not entry_start:
            return None
        next_entry = re.search(r"(?is)<p><ent>.*?</ent><br/", text[entry_start.end() :])
        end = entry_start.end() + next_entry.start() if next_entry else min(len(text), entry_start.end() + 12_000)
        entry = text[entry_start.start() : end]
        definitions = [self._plain_text(value) for value in re.findall(r"(?is)<def>(.*?)</def>", entry)]
        pos_match = re.search(r"(?is)<pos>(.*?)</pos>", entry)
        definition = "; ".join(value for value in definitions[:3] if value)
        if not definition:
            return None
        return {
            "part_of_speech": self._plain_text(pos_match.group(1)) if pos_match else "word",
            "meaning_zh": f"本地英中词典暂无此词；GCIDE 英英释义：{definition}",
            "simple_english": definition,
        }

    @staticmethod
    @lru_cache(maxsize=26)
    def _read_text(path: str) -> str:
        return Path(path).read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _plain_text(value: str) -> str:
        value = re.sub(r"(?i)<br\s*/?>|</(?:div|li|p|ol)>", "\n", value)
        value = re.sub(r"<[^>]+>", "", value)
        return " ".join(html.unescape(value).split())

    @staticmethod
    def _word_candidates(word: str) -> list[str]:
        candidates = [word]
        if " " not in word:
            if word.endswith("ies") and len(word) > 4:
                candidates.append(word[:-3] + "y")
            if word.endswith("es") and len(word) > 3:
                candidates.extend([word[:-2], word[:-1]])
            elif word.endswith("s") and len(word) > 3:
                candidates.append(word[:-1])
            if word.endswith("ied") and len(word) > 4:
                candidates.append(word[:-3] + "y")
            elif word.endswith("ed") and len(word) > 4:
                candidates.extend([word[:-2], word[:-1]])
            if word.endswith("ing") and len(word) > 5:
                stem = word[:-3]
                candidates.extend([stem, stem + "e"])
        return list(dict.fromkeys(candidates))

    @staticmethod
    def _format_result(term: str, headword: str, context: str, result: dict[str, str], source: str) -> dict[str, str]:
        source_label = "FreeDict English-Chinese 2025.11.23" if source == "freedict" else "GNU GCIDE 0.54"
        normalized_note = f"（词典原形：{headword}）" if term.casefold() != headword.casefold() else ""
        return {
            "status": "local_dictionary",
            "provider": "local_dictionary",
            "part_of_speech": result["part_of_speech"],
            "meaning_zh": result["meaning_zh"],
            "context_meaning_zh": f"在本题语境中，{term} 可先按“{result['meaning_zh']}”理解{normalized_note}。",
            "simple_english": result["simple_english"],
            "memory_tip": f"把 {term} 和当前真题原句一起记忆；释义来自本机离线开放词典。",
            "example": context,
            "dictionary_source": source_label,
        }
