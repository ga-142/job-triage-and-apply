"""
Tests for AI response parsing and retry logic.

These tests never touch the real LLM APIs — all network calls are mocked.
The most failure-prone path in the app is the LLM returning unexpected JSON,
so that's the primary focus here.
"""
import json

import pytest

import ai


DUMMY_RESUME = '{"name": "Test User", "skills": ["Python"]}'

VALID_ANALYSIS = json.dumps({
    "score": 85,
    "summary": "Strong match — candidate's Python background fits the role well.",
    "match_reasons": ["Python experience", "Remote-friendly", "FastAPI familiarity"],
})


# ---------------------------------------------------------------------------
# _parse_json
# ---------------------------------------------------------------------------

class TestParseJson:
    def test_clean_json(self):
        raw = '{"score": 85, "summary": "Great", "match_reasons": ["Python"]}'
        result = ai._parse_json(raw)
        assert result["score"] == 85
        assert result["match_reasons"] == ["Python"]

    def test_strips_json_fence(self):
        raw = "```json\n" + VALID_ANALYSIS + "\n```"
        result = ai._parse_json(raw)
        assert result["score"] == 85

    def test_strips_plain_fence(self):
        raw = "```\n" + VALID_ANALYSIS + "\n```"
        result = ai._parse_json(raw)
        assert result["score"] == 85

    def test_handles_leading_trailing_whitespace(self):
        raw = "   \n" + VALID_ANALYSIS + "\n   "
        result = ai._parse_json(raw)
        assert result["score"] == 85

    def test_raises_on_empty_string(self):
        with pytest.raises(ValueError, match="empty"):
            ai._parse_json("")

    def test_raises_on_whitespace_only(self):
        with pytest.raises(ValueError, match="empty"):
            ai._parse_json("   \n  ")

    def test_raises_on_prose(self):
        with pytest.raises(json.JSONDecodeError):
            ai._parse_json("Here is my analysis of the role...")

    def test_raises_on_truncated_json(self):
        with pytest.raises(json.JSONDecodeError):
            ai._parse_json('{"score": 85, "summary": "incomplete...')


# ---------------------------------------------------------------------------
# analyze_job — retry behaviour
# ---------------------------------------------------------------------------

class TestAnalyzeJobRetry:
    """Verify that analyze_job retries on bad output and raises after max attempts."""

    def _make_job(self):
        return {
            "id": "adzuna_test",
            "title": "Software Engineer",
            "company": "Acme",
            "location": "Remote",
            "description": "We use Python and FastAPI.",
            "salary_min": None,
            "salary_max": None,
        }

    def test_succeeds_on_first_try(self, monkeypatch):
        monkeypatch.setattr(ai, "_get_resume", lambda: DUMMY_RESUME)
        monkeypatch.setattr(ai, "_chat", lambda **_: VALID_ANALYSIS)

        result = ai.analyze_job(self._make_job())
        assert result["score"] == 85

    def test_retries_on_bad_json_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(ai, "_get_resume", lambda: DUMMY_RESUME)
        monkeypatch.setattr(ai.time, "sleep", lambda _: None)

        call_count = 0

        def flaky_chat(**_):
            nonlocal call_count
            call_count += 1
            return "not json" if call_count == 1 else VALID_ANALYSIS

        monkeypatch.setattr(ai, "_chat", flaky_chat)

        result = ai.analyze_job(self._make_job())
        assert result["score"] == 85
        assert call_count == 2

    def test_raises_after_max_attempts(self, monkeypatch):
        monkeypatch.setattr(ai, "_get_resume", lambda: DUMMY_RESUME)
        monkeypatch.setattr(ai.time, "sleep", lambda _: None)
        monkeypatch.setattr(ai, "_chat", lambda **_: "always broken")

        with pytest.raises(json.JSONDecodeError):
            ai.analyze_job(self._make_job(), max_attempts=3)

    def test_sleeps_between_retries(self, monkeypatch):
        monkeypatch.setattr(ai, "_get_resume", lambda: DUMMY_RESUME)

        sleep_calls = []
        monkeypatch.setattr(ai.time, "sleep", lambda n: sleep_calls.append(n))

        call_count = 0

        def flaky_chat(**_):
            nonlocal call_count
            call_count += 1
            return "bad" if call_count < 3 else VALID_ANALYSIS

        monkeypatch.setattr(ai, "_chat", flaky_chat)

        ai.analyze_job(self._make_job(), max_attempts=3)
        assert len(sleep_calls) == 2
        assert all(s == 2 for s in sleep_calls)
