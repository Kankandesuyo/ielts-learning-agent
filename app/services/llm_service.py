import json
from typing import Any
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.services.local_dictionary_service import LocalDictionaryService


class LlmClient:
    """Small OpenAI-compatible chat client.

    It keeps the project beginner-friendly:
    - no extra SDK dependency,
    - no API key returned to callers,
    - short timeout and safe fallback when the provider is unavailable.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def enabled(self) -> bool:
        return bool(self.settings.use_llm and self.settings.openai_api_key)

    def supervisor_note(self, profile: dict[str, Any], selected_skill: str, reason: str) -> dict[str, str]:
        if not self.enabled():
            return {"status": "disabled", "text": "LLM is disabled. Rule-based supervisor advice was used."}

        prompt = (
            "You are the main supervisor agent for an IELTS learning product. "
            "Write one concise, practical coaching note for a beginner learner. "
            "Do not claim to be an official IELTS examiner. "
            f"Profile: current band {profile.get('current_band')}, target band {profile.get('target_band')}, "
            f"weak skills {profile.get('weak_skills')}, focus areas {profile.get('focus_areas')}. "
            f"The selected next skill is {selected_skill}. Reason: {reason}. "
            "Return 2-3 short sentences."
        )

        try:
            response = httpx.post(
                f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.openai_model,
                    "messages": [
                        {"role": "system", "content": "You are a clear IELTS learning product manager and coach."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 160,
                },
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"].strip()
            return {"status": "ok", "text": text}
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            return {"status": "fallback", "text": f"LLM call failed safely with HTTP {status_code}. Rule-based supervisor advice was used."}
        except Exception as exc:
            return {"status": "fallback", "text": f"LLM call failed safely: {exc.__class__.__name__}. Rule-based supervisor advice was used."}

    def vocabulary_explanation(self, term: str, context: str) -> dict[str, str]:
        """Explain a selected exam word in Chinese without exposing the key."""
        # Highlight lookups stay private and fast when the bundled open
        # dictionaries contain the selected word.  The LLM/public services are
        # only fallbacks for words missing from the local data.
        if self.settings.local_dictionary_enabled:
            local_result = LocalDictionaryService(self.settings.local_dictionary_dir).lookup(term, context)
            if local_result:
                return local_result
        if not self.enabled():
            if self.settings.public_dictionary_fallback:
                return self._public_dictionary_explanation(term, context)
            return {
                "status": "disabled",
                "provider": "offline",
                "part_of_speech": "待分析",
                "meaning_zh": "模型未启用，暂时无法生成可靠释义。",
                "context_meaning_zh": "请启用后端 LLM 后重试。",
                "simple_english": term,
                "memory_tip": "先结合题目上下文猜测，再查词典核对。",
                "example": context,
            }

        prompt = (
            "Explain the selected IELTS exam vocabulary to a beginner Chinese learner. "
            "Use the meaning in the supplied sentence, not every dictionary meaning. "
            "Return strict JSON with string fields: part_of_speech, meaning_zh, "
            "context_meaning_zh, simple_english, memory_tip, example. "
            "Keep the Chinese concise and make the example an original short English sentence. "
            f"Selected vocabulary: {term}\nSource context: {context}"
        )
        try:
            response = httpx.post(
                f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.openai_model,
                    "messages": [
                        {"role": "system", "content": "You are a precise bilingual IELTS vocabulary teacher."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 360,
                    "response_format": {"type": "json_object"},
                },
                timeout=12,
            )
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"].strip()
            data = json.loads(raw)
            required = ("part_of_speech", "meaning_zh", "context_meaning_zh", "simple_english", "memory_tip", "example")
            return {"status": "ok", "provider": "configured_llm", **{key: str(data.get(key, "")).strip() for key in required}}
        except Exception:
            if self.settings.public_dictionary_fallback:
                return self._public_dictionary_explanation(term, context)
            return {
                "status": "fallback",
                "provider": "offline",
                "part_of_speech": "暂时不可用",
                "meaning_zh": "词汇解释服务暂时不可用，请稍后重试。",
                "context_meaning_zh": "已确认该词来自当前真题语境，但解释服务当前不可用。",
                "simple_english": term,
                "memory_tip": "先看前后句判断褒贬、动作或对象，再核对词义。",
                "example": context,
            }

    @staticmethod
    def _public_dictionary_explanation(term: str, context: str) -> dict[str, str]:
        """No-key fallback for public exam text; no learner data is transmitted."""
        try:
            dictionary_response = httpx.get(
                f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(term.lower())}",
                timeout=8,
            )
            definition = term
            part_of_speech = "phrase"
            example = context
            if dictionary_response.status_code == 200:
                entries = dictionary_response.json()
                meaning = entries[0].get("meanings", [{}])[0]
                definition_item = meaning.get("definitions", [{}])[0]
                definition = str(definition_item.get("definition") or term)
                part_of_speech = str(meaning.get("partOfSpeech") or "word")
                example = str(definition_item.get("example") or context)

            def translate(value: str) -> str:
                response = httpx.get(
                    "https://api.mymemory.translated.net/get",
                    params={"q": value[:450], "langpair": "en|zh-CN"},
                    timeout=8,
                )
                response.raise_for_status()
                return str(response.json().get("responseData", {}).get("translatedText") or "").strip()

            meaning_zh = translate(definition)
            return {
                "status": "dictionary_fallback",
                "provider": "public_dictionary",
                "part_of_speech": part_of_speech,
                "meaning_zh": meaning_zh or "暂未取得中文释义。",
                "context_meaning_zh": f"在这道题里，{term} 表示：{meaning_zh}",
                "simple_english": definition,
                "memory_tip": f"把 {term} 与本题原句一起记忆，不要只背孤立中文。",
                "example": example,
            }
        except Exception:
            return {
                "status": "fallback",
                "provider": "offline",
                "part_of_speech": "暂时不可用",
                "meaning_zh": "词汇解释服务暂时不可用，请稍后重试。",
                "context_meaning_zh": "词汇已确认来自 database 真题，但公开词典暂时无法访问。",
                "simple_english": term,
                "memory_tip": "先根据前后文猜测词义，再使用可靠词典核对。",
                "example": context,
            }
