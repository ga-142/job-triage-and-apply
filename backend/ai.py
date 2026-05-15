import json
import logging
import os
import re
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

RESUME_PATH                = Path(__file__).parent / "resume.txt"
_RESUME_PATH_LEGACY        = Path(__file__).parent / "resume.json"   # backward compat
WRITING_SAMPLE_PATH        = Path(__file__).parent / "writing_sample.txt"
DOCUMENT_INSTRUCTIONS_PATH = Path(__file__).parent / "document_instructions.txt"

# ---------------------------------------------------------------------------
# Provider configuration
#
# SCORING_PROVIDER  — LLM used for analyze_job() (fast, cheap, local-friendly)
# DOCUMENT_PROVIDER — LLM used for resume and cover letter generation
#                     (quality matters; a stronger model is recommended)
#
# Both fall back to LLM_PROVIDER so existing .env files keep working unchanged.
# Valid values: "anthropic" | "openai" | "ollama"
# ---------------------------------------------------------------------------
_default_provider = os.getenv("LLM_PROVIDER", "anthropic").lower()

SCORING_PROVIDER  = os.getenv("SCORING_PROVIDER",  _default_provider).lower()
DOCUMENT_PROVIDER = os.getenv("DOCUMENT_PROVIDER", _default_provider).lower()

ANTHROPIC_MODEL          = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
OPENAI_MODEL             = os.getenv("OPENAI_MODEL",    "gpt-4o")
OLLAMA_BASE_URL          = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL             = os.getenv("OLLAMA_MODEL",    "qwen2.5:7b")
WRITING_SAMPLE_MAX_WORDS = int(os.getenv("WRITING_SAMPLE_MAX_WORDS", "400"))

# Module-level singletons — constructed lazily so missing env vars only
# raise at call time, not at import time.
_anthropic_client = None
_openai_client    = None
_resume_text: str | None = None
_writing_sample_loaded = False
_writing_sample_text: str | None = None
_document_instructions_loaded = False
_document_instructions_text: str | None = None


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic
        _anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _anthropic_client


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _openai_client


def _get_resume() -> str:
    global _resume_text
    if _resume_text is None:
        path = RESUME_PATH if RESUME_PATH.exists() else _RESUME_PATH_LEGACY
        if not path.exists():
            raise FileNotFoundError(
                "Resume not found. Create backend/resume.txt with your resume content "
                "before running scans."
            )
        _resume_text = path.read_text()
    return _resume_text


def _get_writing_sample() -> str | None:
    """Return the writing sample truncated to WRITING_SAMPLE_MAX_WORDS words.

    Returns None if writing_sample.txt does not exist. Result is cached so the
    file is only read once per process lifetime.
    """
    global _writing_sample_loaded, _writing_sample_text
    if not _writing_sample_loaded:
        _writing_sample_loaded = True
        if WRITING_SAMPLE_PATH.exists():
            text = WRITING_SAMPLE_PATH.read_text().strip()
            if text:
                words = text.split()
                if len(words) > WRITING_SAMPLE_MAX_WORDS:
                    text = " ".join(words[:WRITING_SAMPLE_MAX_WORDS]) + "…"
                _writing_sample_text = text
    return _writing_sample_text


def _get_document_instructions() -> str | None:
    """Return custom document generation instructions from document_instructions.txt.

    Returns None if the file does not exist. Result is cached so the file is
    only read once per process lifetime.
    """
    global _document_instructions_loaded, _document_instructions_text
    if not _document_instructions_loaded:
        _document_instructions_loaded = True
        if DOCUMENT_INSTRUCTIONS_PATH.exists():
            text = DOCUMENT_INSTRUCTIONS_PATH.read_text().strip()
            if text:
                _document_instructions_text = text
    return _document_instructions_text


def invalidate_resume_cache() -> None:
    global _resume_text
    _resume_text = None


def invalidate_writing_sample_cache() -> None:
    global _writing_sample_loaded, _writing_sample_text
    _writing_sample_loaded = False
    _writing_sample_text = None


def invalidate_document_instructions_cache() -> None:
    global _document_instructions_loaded, _document_instructions_text
    _document_instructions_loaded = False
    _document_instructions_text = None


def _parse_json(raw: str) -> dict:
    """Strip optional markdown fences then parse JSON."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    if not text:
        raise ValueError("LLM returned an empty response")
    return json.loads(text)


# ---------------------------------------------------------------------------
# Low-level LLM dispatch
# ---------------------------------------------------------------------------

def _chat_anthropic(system_text: str, user_text: str, max_tokens: int) -> str:
    """Call the Anthropic API with prompt caching on the system prompt.

    cache_control:ephemeral means the resume (large, constant) is only
    tokenised once per 5-minute cache window — cuts cost on bulk scans.
    """
    resp = _get_anthropic().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_text}],
    )
    return resp.content[0].text


def _chat_openai(system_text: str, user_text: str, max_tokens: int) -> str:
    resp = _get_openai().chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_text},
            {"role": "user",   "content": user_text},
        ],
    )
    return resp.choices[0].message.content


def _chat_ollama(system_text: str, user_text: str, max_tokens: int) -> str:
    """Call a local Ollama instance. Timeout is generous — CPU inference is slow."""
    resp = httpx.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user",   "content": user_text},
            ],
            "stream": False,
            "options": {"num_predict": max_tokens},
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _chat(system_text: str, user_text: str, max_tokens: int = 1024, *, provider: str) -> str:
    """Dispatch to the requested LLM provider."""
    logger.debug(
        "LLM request [provider=%s]\n--- SYSTEM ---\n%s\n--- USER ---\n%s\n--- END ---",
        provider, system_text, user_text,
    )
    if provider == "openai":
        return _chat_openai(system_text, user_text, max_tokens)
    if provider == "ollama":
        return _chat_ollama(system_text, user_text, max_tokens)
    return _chat_anthropic(system_text, user_text, max_tokens)


# ---------------------------------------------------------------------------
# Shared prompt pieces
# ---------------------------------------------------------------------------

_SCORING_ROLE = """\
You are a job match analyst. Evaluate whether a job listing is a good match \
for the candidate based on their resume.

When given a job listing respond with a JSON object only — no prose, no \
markdown fences — in exactly this format:
{
  "score": <integer 1-100>,
  "summary": "<two sentence summary of the role and why it does or does not fit>",
  "match_reasons": ["<bullet 1>", "<bullet 2>", "<bullet 3>"]
}

Scoring guide:
- 90-100: Near-perfect match, candidate clearly qualified and role aligns with their goals
- 70-89: Good match with minor gaps
- 50-69: Partial match, some relevant experience but notable gaps
- Below 50: Poor match

Provide 3-5 match_reasons. Be specific — reference actual skills, experience, \
or role requirements."""

_DOCUMENT_ROLE = """\
You are a career document specialist. Use the candidate's resume to produce \
tailored job application materials."""


def _system(role: str, include_writing_sample: bool = False) -> str:
    """Assemble the system prompt: role description + resume + optional writing sample and instructions."""
    parts = [role, f"\n\nCandidate resume:\n<resume>\n{_get_resume()}\n</resume>"]
    if include_writing_sample:
        sample = _get_writing_sample()
        if sample:
            parts.append(
                f"\n\nCandidate writing sample — mirror this tone and voice in all documents:\n"
                f"<writing_sample>\n{sample}\n</writing_sample>"
            )
        instructions = _get_document_instructions()
        if instructions:
            parts.append(
                f"\n\nAdditional instructions for all documents you produce:\n"
                f"<document_instructions>\n{instructions}\n</document_instructions>"
            )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _model_for(provider: str) -> str:
    return {"anthropic": ANTHROPIC_MODEL, "openai": OPENAI_MODEL, "ollama": OLLAMA_MODEL}.get(provider, provider)


def analyze_job(job: dict, max_attempts: int = 3) -> dict:
    logger.info("analyze_job provider=%s model=%s", SCORING_PROVIDER, _model_for(SCORING_PROVIDER))
    listing = (
        f"Title: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
        f"Description: {job['description']}\n"
        f"Salary: {job.get('salary_min', 'N/A')} - {job.get('salary_max', 'N/A')}"
    )
    for attempt in range(1, max_attempts + 1):
        try:
            raw = _chat(
                system_text=_system(_SCORING_ROLE),
                user_text=f"Analyze this job listing:\n\n{listing}",
                max_tokens=1024,
                provider=SCORING_PROVIDER,
            )
            logger.debug("analyze_job raw: %s", raw)
            return _parse_json(raw)
        except Exception as exc:
            logger.warning(
                "analyze_job attempt %d/%d failed for %s — %s: %s",
                attempt, max_attempts, job.get("id"), type(exc).__name__, exc,
            )
            if attempt < max_attempts:
                time.sleep(2)
            else:
                raise


def generate_resume(job: dict) -> dict:
    logger.info("generate_resume provider=%s model=%s", DOCUMENT_PROVIDER, _model_for(DOCUMENT_PROVIDER))
    listing = (
        f"Title: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
        f"Description: {job['description']}"
    )
    prompt = f"""\
Write a tailored resume for the candidate applying to this job.
Output a JSON object only — no prose, no markdown fences — in exactly this format:
{{
  "name": "...",
  "contact": "...",
  "summary": "...",
  "experience": [
    {{
      "company": "...",
      "title": "...",
      "dates": "...",
      "bullets": ["...", "..."]
    }}
  ],
  "skills": ["...", "..."],
  "education": [
    {{
      "school": "...",
      "degree": "...",
      "year": "..."
    }}
  ]
}}

Rules:
- contact: combine email, phone, LinkedIn separated by " | ", omit any that are absent
- summary: 2-3 sentences tailored to this specific role and company
- experience: preserve the exact order from the resume; within each role, \
reorder bullets to lead with those most relevant to this job
- skills: include all skills, most relevant first

Job posting:
{listing}"""

    raw = _chat(
        system_text=_system(_DOCUMENT_ROLE, include_writing_sample=True),
        user_text=prompt,
        max_tokens=2048,
        provider=DOCUMENT_PROVIDER,
    )
    logger.debug("generate_resume raw: %s", raw)
    return _parse_json(raw)


def generate_cover_letter(job: dict) -> str:
    logger.info("generate_cover_letter provider=%s model=%s", DOCUMENT_PROVIDER, _model_for(DOCUMENT_PROVIDER))
    listing = (
        f"Title: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
        f"Description: {job['description']}"
    )
    prompt = f"""\
Write a professional cover letter for the candidate applying to this job.
Output the letter text only — no JSON, no extra explanation, no markdown.

Instructions:
- Greeting: scan the job description for a specific contact name; if found \
use "Dear [Name]", otherwise "Dear Hiring Manager at {job['company']}"
- Opening paragraph: genuine interest in the specific role and company
- Middle paragraphs (2): connect the candidate's most relevant experience \
and skills to the job requirements
- Closing paragraph: call to action and enthusiasm
- Sign off with the candidate's name from their resume
- Do not invent facts not present in the resume

Job posting:
{listing}"""

    raw = _chat(
        system_text=_system(_DOCUMENT_ROLE, include_writing_sample=True),
        user_text=prompt,
        max_tokens=1024,
        provider=DOCUMENT_PROVIDER,
    )
    return raw.strip()
