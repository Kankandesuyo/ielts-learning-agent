import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

TEST_DIR = Path(tempfile.mkdtemp(prefix="ielts-agent-tests-"))
os.environ["USE_LLM"] = "false"
os.environ["PUBLIC_DICTIONARY_FALLBACK"] = "false"
os.environ["LOCAL_DICTIONARY_ENABLED"] = "true"
os.environ["LOCAL_DICTIONARY_DIR"] = "database/legal-dictionaries"
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_DIR / 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(TEST_DIR / "uploads")
os.environ["MAX_UPLOAD_MB"] = "1"

from app.database import engine, init_db
from app.main import app


init_db()
client = TestClient(app)
ACCOUNT_SEQUENCE = 0
ACCOUNT_CREDENTIALS: dict[int, tuple[str, str]] = {}


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_runtime():
    yield
    engine.dispose()
    shutil.rmtree(TEST_DIR, ignore_errors=True)


def create_profile() -> int:
    global ACCOUNT_SEQUENCE
    ACCOUNT_SEQUENCE += 1
    email = f"learner{ACCOUNT_SEQUENCE}@example.com"
    password = f"Secure-pass-{ACCOUNT_SEQUENCE}!"
    registered = client.post("/auth/register", json={"email": email, "password": password})
    assert registered.status_code == 201
    client.headers["X-CSRF-Token"] = client.cookies.get("ielts_csrf")
    response = client.post(
        "/profile/create",
        json={
            "current_band": 5.5,
            "target_band": 6.5,
            "prep_days": 30,
            "daily_minutes": 120,
            "weak_skills": ["Writing", "Speaking"],
            "focus_areas": ["grammar", "writing logic"],
        },
    )
    assert response.status_code == 200
    profile_id = response.json()["id"]
    ACCOUNT_CREDENTIALS[profile_id] = (email, password)
    return profile_id


def login_as(profile_id: int) -> None:
    email, password = ACCOUNT_CREDENTIALS[profile_id]
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = client.cookies.get("ielts_csrf")


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_authentication_session_csrf_and_logout():
    browser = TestClient(app)
    assert browser.get("/auth/status").json()["authenticated"] is False
    assert browser.get("/auth/me").status_code == 401

    credentials = {"email": "auth-check@example.com", "password": "A-secure-password!"}
    registered = browser.post("/auth/register", json=credentials)
    assert registered.status_code == 201
    assert registered.json()["profile_id"] is None
    assert browser.cookies.get("ielts_session")
    csrf_token = browser.cookies.get("ielts_csrf")
    assert csrf_token
    assert browser.get("/auth/status").json()["authenticated"] is True

    profile_payload = {
        "current_band": 5.0,
        "target_band": 6.5,
        "prep_days": 30,
        "daily_minutes": 90,
        "weak_skills": ["writing"],
        "focus_areas": ["grammar"],
    }
    assert browser.post("/profile/create", json=profile_payload).status_code == 403
    browser.headers["X-CSRF-Token"] = csrf_token
    created = browser.post("/profile/create", json=profile_payload)
    assert created.status_code == 200
    profile_id = created.json()["id"]
    assert browser.get("/auth/me").json()["profile_id"] == profile_id
    assert browser.get(f"/profile/{profile_id + 1}").status_code == 403

    duplicate = browser.post("/auth/register", json=credentials)
    assert duplicate.status_code == 409
    assert browser.post("/auth/login", json={**credentials, "password": "wrong-password"}).status_code == 401
    assert browser.post("/auth/logout").status_code == 204
    assert browser.get("/auth/status").json()["authenticated"] is False
    assert browser.get("/auth/me").status_code == 401


def test_core_learning_flow():
    user_id = create_profile()

    plan = client.post("/study-plan/generate", json={"user_id": user_id, "days": 2})
    assert plan.status_code == 200
    assert len(plan.json()["plan"]) == 2
    plan_id = plan.json()["plan_id"]

    latest_plan = client.get(f"/study-plan/{user_id}/latest")
    assert latest_plan.status_code == 200
    assert latest_plan.json()["progress_percent"] == 0

    completed = client.patch(
        f"/study-plan/{user_id}/{plan_id}/days/1",
        json={"completed": True},
    )
    assert completed.status_code == 200
    assert completed.json()["completed_days"] == 1
    assert completed.json()["progress_percent"] == 50
    assert completed.json()["plan"][0]["completed"] is True

    writing = client.post(
        "/writing/review",
        json={
            "user_id": user_id,
            "task_type": "Task 2",
            "essay_text": "Education is important because it helps people get better jobs. "
            "Many students study online because online study is flexible and useful. "
            "However, some students need teachers because they cannot manage time well. "
            "In my opinion, schools should combine online learning and classroom learning.",
        },
    )
    assert writing.status_code == 200
    assert "estimated_band_score" in writing.json()

    speaking = client.post(
        "/speaking/practice",
        json={"user_id": user_id, "part": 1, "answer_text": "I study software engineering. I like it because I can build useful tools for students."},
    )
    assert speaking.status_code == 200

    supervisor = client.post("/supervisor/diagnose", json={"user_id": user_id})
    assert supervisor.status_code == 200
    assert supervisor.json()["current_learning_priority"] == "writing"
    assert "writing_agent" in supervisor.json()["agent_team"]

    coached = client.post(
        "/supervisor/coach",
        json={
            "user_id": user_id,
            "skill_focus": "speaking",
            "learner_input": "I study software engineering because I want to build useful learning products.",
            "speaking_part": 1,
        },
    )
    assert coached.status_code == 200
    assert coached.json()["supervisor_decision"]["selected_agent"] == "speaking_agent"

    errors = client.get(f"/errors/{user_id}")
    assert errors.status_code == 200
    assert len(errors.json()["items"]) >= 1


def test_document_upload_flow():
    user_id = create_profile()

    upload = client.post(
        "/documents/upload",
        data={"user_id": str(user_id), "category": "notes", "notes": "test upload"},
        files={"file": ("sample.txt", b"IELTS reading note", "text/plain")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["item"]["id"]

    listed = client.get(f"/documents/{user_id}")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["original_filename"] == "sample.txt"

    downloaded = client.get(f"/documents/{user_id}/{document_id}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == b"IELTS reading note"

    deleted = client.delete(f"/documents/{user_id}/{document_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_database_material_question_and_analysis_flow():
    user_id = create_profile()
    profile = client.put(
        f"/profile/{user_id}",
        json={
            "current_band": 5.5,
            "target_band": 6.5,
            "prep_days": 30,
            "daily_minutes": 90,
            "weak_skills": ["Reading"],
            "focus_areas": ["environment"],
        },
    )
    assert profile.status_code == 200

    status = client.get("/knowledge/status")
    assert status.status_code == 200
    assert status.json()["supported_files"] >= 1
    assert status.json()["indexed"] is True

    generated = client.post(
        "/knowledge/question",
        json={"user_id": user_id, "skill": "auto", "topic": "environment"},
    )
    assert generated.status_code == 200
    question = generated.json()
    assert question["question_id"] > 0
    assert question["source"]["book"].lower().endswith(".pdf")
    assert question["source"]["page"] > 0
    assert "_____" in question["question"]

    analyzed = client.post(
        "/knowledge/analyze",
        json={"user_id": user_id, "question_id": question["question_id"], "answer": "deliberately wrong"},
    )
    assert analyzed.status_code == 200
    assert analyzed.json()["correct"] is False
    assert analyzed.json()["correct_answer"]


def test_full_reading_exam_flow():
    user_id = create_profile()
    started = client.get("/exam/reading/start")
    assert started.status_code == 200
    paper = started.json()
    assert paper["total_questions"] == 40
    assert paper["duration_minutes"] == 60
    assert len(paper["sections"]) == 3
    assert paper["sections"][0]["question_numbers"] == list(range(1, 14))
    assert paper["sections"][0]["question_pages"] == [18, 19]
    first_section = paper["sections"][0]
    assert first_section["passage_number"] == 1
    assert first_section["article_title"] == "Why we need to protect polar bears"
    assert first_section["question_label"] == "Questions 1-13"
    assert first_section["recommended_minutes"] == 20
    assert first_section["passage"].startswith("Polar bears are being increasingly threatened")
    assert not first_section["passage"].startswith("Test 1 READING")
    assert "16 Reading" not in first_section["passage"]
    assert "18 Questions 8-13" not in first_section["questions"]
    assert not paper["sections"][1]["questions"].startswith("READING PASSAGE 2")
    assert "Test 1 Questions 35-40" not in paper["sections"][2]["questions"]

    explained = client.post(
        "/exam/vocabulary/explain",
        json={"term": "contradicts", "section_index": 0, "area": "questions"},
    )
    assert explained.status_code == 200
    explanation = explained.json()
    assert explanation["term"] == "contradicts"
    assert "contradicts" in explanation["context"].lower()
    assert explanation["source"]["book"].lower().endswith(".pdf")
    assert explanation["source"]["pages"] == [18, 19]
    assert explanation["source"]["section_index"] == 0
    assert explanation["source"]["area"] == "questions"
    assert explanation["provider"] == "local_dictionary"
    # "contradicts" is normalized to its headword and resolved by the local
    # GCIDE fallback when the bilingual FreeDict data has no inflected entry.
    assert explanation["dictionary_source"] == "GNU GCIDE 0.54"
    assert explanation["meaning_zh"]

    # A stale browser section index must not reject vocabulary that is still
    # present in the authoritative database-backed question paper.
    recovered = client.post(
        "/exam/vocabulary/explain",
        json={"term": "contradicts", "section_index": 1, "area": "questions"},
    )
    assert recovered.status_code == 200
    assert recovered.json()["source"]["section_index"] == 0

    passage_word = client.post(
        "/exam/vocabulary/explain",
        json={"term": "Arctic", "section_index": 0, "area": "passage"},
    )
    assert passage_word.status_code == 200
    assert passage_word.json()["source"]["pages"] == [16, 17]
    assert passage_word.json()["source"]["area"] == "passage"

    fabricated = client.post(
        "/exam/vocabulary/explain",
        json={"term": "fabricatedword", "section_index": 0, "area": "questions"},
    )
    assert fabricated.status_code == 422

    answers = {str(number): "" for number in range(1, 41)}
    answers.update({"1": "FALSE", "2": "FALSE", "3": "NOT GIVEN", "25": "B", "26": "D"})
    submitted = client.post("/exam/reading/submit", json={"user_id": user_id, "answers": answers})
    assert submitted.status_code == 200
    result = submitted.json()
    assert result["raw_score"] == 5
    assert len(result["details"]) == 40


def test_exam_chrome_cleanup_is_not_tied_to_test_one():
    from app.services.exam_service import ReadingExamService

    passage = (
        "Test 2 ACADEMIC READING READING PASSAGE 1 "
        "You should spend about 20 minutes on Questions 1-13, which are based on Reading Passage 1 below. "
        "A completely different article New source-backed body text. 105 Reading The body continues. 106"
    )
    cleaned = ReadingExamService._strip_passage_chrome(
        passage,
        passage_number=1,
        article_title="A completely different article",
    )
    assert cleaned == "New source-backed body text. The body continues."

    questions = "Test 4 Questions 1-7 First group. 105 Test 4 Questions 8-13 Second group."
    assert ReadingExamService._strip_question_chrome(questions) == (
        "Questions 1-7 First group. Questions 8-13 Second group."
    )

    second_passage_questions = (
        "Test 6 READING PASSAGE 2 You should spend about 20 minutes on Questions 14-26, "
        "which are based on Reading Passage 2 on pages 21 and 22. Questions 14-20 Start here."
    )
    assert ReadingExamService._strip_question_chrome(second_passage_questions) == (
        "Questions 14-20 Start here."
    )


def test_knowledge_excerpt_cleanup_supports_other_books_and_tests():
    from app.services.knowledge_service import KnowledgeService

    raw = (
        "CAMBRIDGE University Press https://example.test Test 3 READING READING PASSAGE 2 "
        "You should spend about 20 minutes on Questions 14 – 26, which are based on "
        "Reading Passage 2 on pages 40 and 41. A new article A new article starts here. "
        "105 Test 3 The article continues."
    )
    assert KnowledgeService._clean_source_excerpt(raw) == (
        "A new article A new article starts here. The article continues."
    )


def test_local_bilingual_dictionary_parses_stardict_data():
    from app.services.local_dictionary_service import LocalDictionaryService

    result = LocalDictionaryService().lookup("apple", "The apple is on the table.")
    assert result is not None
    assert result["provider"] == "local_dictionary"
    assert result["dictionary_source"].startswith("FreeDict")
    assert "苹果" in result["meaning_zh"]
    assert result["part_of_speech"] == "noun"


def test_profile_read_update_and_delete():
    user_id = create_profile()

    plan = client.post("/study-plan/generate", json={"user_id": user_id, "days": 1})
    assert plan.status_code == 200
    upload = client.post(
        "/documents/upload",
        data={"user_id": str(user_id), "category": "notes", "notes": "delete with profile"},
        files={"file": ("profile-note.txt", b"profile cleanup", "text/plain")},
    )
    assert upload.status_code == 200

    loaded = client.get(f"/profile/{user_id}")
    assert loaded.status_code == 200
    assert loaded.json()["weak_skills"] == ["writing", "speaking"]

    updated = client.put(
        f"/profile/{user_id}",
        json={
            "current_band": 6.0,
            "target_band": 7.0,
            "prep_days": 45,
            "daily_minutes": 90,
            "weak_skills": ["reading"],
            "focus_areas": ["time management"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["current_band"] == 6.0
    assert updated.json()["weak_skills"] == ["reading"]

    deleted = client.delete(f"/profile/{user_id}")
    assert deleted.status_code == 200
    assert client.get(f"/profile/{user_id}").status_code == 403
    assert client.get(f"/study-plan/{user_id}/latest").status_code == 403
    assert not list((TEST_DIR / "uploads").glob("*"))


def test_validation_and_upload_security_boundaries():
    invalid_profile = client.post(
        "/profile/create",
        json={
            "current_band": 7.0,
            "target_band": 6.0,
            "prep_days": 30,
            "daily_minutes": 60,
            "weak_skills": ["hacking"],
            "focus_areas": [],
        },
    )
    assert invalid_profile.status_code == 422

    user_id = create_profile()
    fake_pdf = client.post(
        "/documents/upload",
        data={"user_id": str(user_id), "category": "notes", "notes": "fake"},
        files={"file": ("fake.pdf", b"not a real pdf", "application/pdf")},
    )
    assert fake_pdf.status_code == 400

    oversized = client.post(
        "/documents/upload",
        data={"user_id": str(user_id), "category": "notes", "notes": "large"},
        files={"file": ("large.txt", b"a" * (1024 * 1024 + 1), "text/plain")},
    )
    assert oversized.status_code == 413

    invalid_skill = client.post(
        "/supervisor/coach",
        json={"user_id": user_id, "skill_focus": "admin", "speaking_part": 1},
    )
    assert invalid_skill.status_code == 422


def test_frontend_and_static_assets_are_served():
    """The learner-facing page is a product surface, not just a health API."""
    frontend = client.get("/")
    assert frontend.status_code == 200
    assert "IELTS" in frontend.text
    assert "text/html" in frontend.headers["content-type"]

    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert "application/javascript" in script.headers["content-type"]


def test_direct_practice_and_vocabulary_routes_save_expected_results():
    """Cover the three direct learning modules that the original flow skipped."""
    user_id = create_profile()

    reading_prompt = client.post("/reading/practice", json={"user_id": user_id})
    assert reading_prompt.status_code == 200
    assert "question" in reading_prompt.json()

    reading_answer = client.post(
        "/reading/practice",
        json={"user_id": user_id, "question_type": "True / False / Not Given", "user_answer": "False"},
    )
    assert reading_answer.status_code == 200
    assert reading_answer.json()["correct"] is False

    listening_prompt = client.post("/listening/practice", json={"user_id": user_id})
    assert listening_prompt.status_code == 200
    assert listening_prompt.json()["audio_ready"] is False

    listening_answer = client.post(
        "/listening/practice",
        json={"user_id": user_id, "scenario": "library", "user_answer": "9:30"},
    )
    assert listening_answer.status_code == 200
    assert listening_answer.json()["correct"] is False

    vocabulary = client.post(
        "/vocabulary/generate",
        json={"user_id": user_id, "topic": "technology", "count": 3},
    )
    assert vocabulary.status_code == 200
    assert [item["word"] for item in vocabulary.json()["items"]] == ["innovation", "automation", "privacy"]

    sources = {item["source"] for item in client.get(f"/errors/{user_id}").json()["items"]}
    assert {"reading", "listening"}.issubset(sources)


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/study-plan/generate", {"user_id": 999_999, "days": 1}),
        ("post", "/writing/review", {"user_id": 999_999, "essay_text": "A valid-length essay that belongs to nobody."}),
        ("post", "/speaking/practice", {"user_id": 999_999}),
        ("post", "/reading/practice", {"user_id": 999_999}),
        ("post", "/listening/practice", {"user_id": 999_999}),
        ("post", "/vocabulary/generate", {"user_id": 999_999, "topic": "education", "count": 2}),
        ("post", "/supervisor/diagnose", {"user_id": 999_999}),
        ("post", "/supervisor/coach", {"user_id": 999_999}),
        ("post", "/knowledge/question", {"user_id": 999_999, "skill": "reading"}),
        ("post", "/exam/reading/submit", {"user_id": 999_999, "answers": {}}),
    ],
)
def test_profile_scoped_routes_reject_other_user_ids(method, path, payload):
    response = client.request(method, path, json=payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "无权访问其他用户的数据。"


def test_study_plan_not_found_and_completion_reversal():
    user_id = create_profile()
    assert client.get(f"/study-plan/{user_id}/latest").status_code == 404
    assert client.patch(f"/study-plan/{user_id}/999999/days/1", json={"completed": True}).status_code == 404

    generated = client.post("/study-plan/generate", json={"user_id": user_id, "days": 1}).json()
    plan_id = generated["plan_id"]
    assert client.patch(f"/study-plan/{user_id}/{plan_id}/days/2", json={"completed": True}).status_code == 404

    completed = client.patch(f"/study-plan/{user_id}/{plan_id}/days/1", json={"completed": True})
    assert completed.json()["progress_percent"] == 100
    reopened = client.patch(f"/study-plan/{user_id}/{plan_id}/days/1", json={"completed": False})
    assert reopened.status_code == 200
    assert reopened.json()["progress_percent"] == 0
    assert reopened.json()["plan"][0]["completed_at"] is None


def test_document_ownership_and_additional_upload_boundaries():
    owner_id = create_profile()
    other_id = create_profile()
    login_as(owner_id)
    uploaded = client.post(
        "/documents/upload",
        data={"user_id": str(owner_id), "category": "notes", "notes": "private"},
        files={"file": ("private.txt", b"owner only", "text/plain")},
    )
    assert uploaded.status_code == 200
    document_id = uploaded.json()["item"]["id"]

    assert client.get(f"/documents/{other_id}/{document_id}/download").status_code == 403
    assert client.delete(f"/documents/{other_id}/{document_id}").status_code == 403
    assert client.get("/documents/999999").status_code == 403

    cases = [
        (("malware.exe", b"unsafe", "application/octet-stream"), "notes", "", 400),
        (("empty.txt", b"", "text/plain"), "notes", "", 400),
        (("binary.txt", b"bad\x00text", "text/plain"), "notes", "", 400),
        (("note.txt", b"valid", "text/plain"), "admin", "", 400),
        (("note.txt", b"valid", "text/plain"), "notes", "x" * 501, 400),
    ]
    for file_value, category, notes, expected in cases:
        response = client.post(
            "/documents/upload",
            data={"user_id": str(owner_id), "category": category, "notes": notes},
            files={"file": file_value},
        )
        assert response.status_code == expected


def test_knowledge_correct_answer_and_question_ownership():
    owner_id = create_profile()
    other_id = create_profile()
    login_as(owner_id)
    generated = client.post(
        "/knowledge/question",
        json={"user_id": owner_id, "skill": "reading", "topic": "environment"},
    )
    assert generated.status_code == 200
    question_id = generated.json()["question_id"]

    login_as(other_id)
    denied = client.post(
        "/knowledge/analyze",
        json={"user_id": other_id, "question_id": question_id, "answer": "anything"},
    )
    assert denied.status_code == 404

    login_as(owner_id)
    wrong = client.post(
        "/knowledge/analyze",
        json={"user_id": owner_id, "question_id": question_id, "answer": "wrong"},
    )
    assert wrong.status_code == 200
    correct = client.post(
        "/knowledge/analyze",
        json={"user_id": owner_id, "question_id": question_id, "answer": wrong.json()["correct_answer"]},
    )
    assert correct.status_code == 200
    assert correct.json()["correct"] is True


def test_supervisor_routes_to_each_remaining_skill():
    user_id = create_profile()
    cases = {
        "reading": "False",
        "listening": "9:30",
        "writing": "Online education can improve access, but students still need clear feedback from teachers.",
    }
    for skill, learner_input in cases.items():
        response = client.post(
            "/supervisor/coach",
            json={"user_id": user_id, "skill_focus": skill, "learner_input": learner_input},
        )
        assert response.status_code == 200
        assert response.json()["supervisor_decision"]["selected_skill"] == skill


def test_supervisor_without_input_generates_a_source_backed_question():
    user_id = create_profile()
    profile = client.put(
        f"/profile/{user_id}",
        json={
            "current_band": 5.0,
            "target_band": 6.5,
            "prep_days": 30,
            "daily_minutes": 90,
            "weak_skills": ["reading"],
            "focus_areas": ["environment"],
        },
    )
    assert profile.status_code == 200
    response = client.post("/supervisor/coach", json={"user_id": user_id})
    assert response.status_code == 200
    result = response.json()
    assert result["supervisor_decision"]["selected_skill"] == "reading"
    assert result["skill_agent_result"]["question_id"] > 0
    assert result["skill_agent_result"]["source"]["page"] > 0


def test_rag_service_handles_missing_documents_and_ranks_matches(tmp_path):
    from app.services.rag_service import RagService

    missing = RagService(str(tmp_path / "missing"))
    assert missing.load_documents() == []
    assert missing.retrieve("writing grammar") == []

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "writing.md").write_text("Writing grammar and coherence.\n\nUse examples to support writing ideas.", encoding="utf-8")
    (docs / "reading.md").write_text("Reading requires locating words.", encoding="utf-8")
    rag = RagService(str(docs))
    results = rag.retrieve("writing coherence", top_k=1)
    assert len(results) == 1
    assert results[0]["source"].endswith("writing.md")
    assert results[0]["score"] == 2


def test_llm_client_disabled_mode_never_calls_an_external_provider():
    from app.services.llm_service import LlmClient

    llm = LlmClient()
    llm.settings = SimpleNamespace(
        use_llm=False,
        openai_api_key=None,
        local_dictionary_enabled=False,
        local_dictionary_dir="unused",
        public_dictionary_fallback=False,
    )
    assert llm.enabled() is False
    assert llm.supervisor_note({}, "writing", "test")["status"] == "disabled"
    explanation = llm.vocabulary_explanation("example", "An example sentence.")
    assert explanation["status"] == "disabled"
    assert explanation["provider"] == "offline"


def test_configured_llm_success_and_safe_network_failure(monkeypatch):
    import httpx

    from app.services.llm_service import LlmClient

    llm = LlmClient()
    llm.settings = SimpleNamespace(
        use_llm=True,
        openai_api_key="test-only-key",
        openai_base_url="https://llm.invalid/v1",
        openai_model="test-model",
        local_dictionary_enabled=False,
        local_dictionary_dir="unused",
        public_dictionary_fallback=False,
    )

    class SuccessfulResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "Keep practising one focused reading skill."}}]}

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: SuccessfulResponse())
    note = llm.supervisor_note({"current_band": 5.5, "target_band": 6.5}, "reading", "weak skill")
    assert note == {"status": "ok", "text": "Keep practising one focused reading skill."}

    def fail_request(*args, **kwargs):
        raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr(httpx, "post", fail_request)
    fallback = llm.supervisor_note({}, "writing", "default")
    assert fallback["status"] == "fallback"
    assert "ConnectError" in fallback["text"]
    assert "test-only-key" not in fallback["text"]


def test_configured_llm_vocabulary_json_and_malformed_response_fallback(monkeypatch):
    import json
    import httpx

    from app.services.llm_service import LlmClient

    llm = LlmClient()
    llm.settings = SimpleNamespace(
        use_llm=True,
        openai_api_key="test-only-key",
        openai_base_url="https://llm.invalid/v1",
        openai_model="test-model",
        local_dictionary_enabled=False,
        local_dictionary_dir="unused",
        public_dictionary_fallback=False,
    )
    vocabulary_payload = {
        "part_of_speech": "noun",
        "meaning_zh": "例子",
        "context_meaning_zh": "在句中表示例子",
        "simple_english": "something that illustrates an idea",
        "memory_tip": "与句子一起记忆",
        "example": "This is an example.",
    }

    class VocabularyResponse:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": self.content}}]}

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: VocabularyResponse(json.dumps(vocabulary_payload)))
    success = llm.vocabulary_explanation("example", "This is an example.")
    assert success["status"] == "ok"
    assert success["provider"] == "configured_llm"
    assert success["meaning_zh"] == "例子"

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: VocabularyResponse("not json"))
    fallback = llm.vocabulary_explanation("example", "This is an example.")
    assert fallback["status"] == "fallback"
    assert fallback["provider"] == "offline"


def test_frontend_security_script_is_part_of_the_test_suite():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed; frontend security check cannot run.")
    completed = subprocess.run(
        [node, "tests/frontend_security_test.js"],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Frontend XSS escaping checks passed." in completed.stdout
