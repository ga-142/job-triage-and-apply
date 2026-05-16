import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

load_dotenv()

from ai import (
    DOCUMENT_INSTRUCTIONS_PATH,
    RESUME_PATH,
    WRITING_SAMPLE_PATH,
    generate_cover_letter,
    generate_resume,
    invalidate_document_instructions_cache,
    invalidate_resume_cache,
    invalidate_writing_sample_cache,
)
from database import (
    get_all_settings,
    get_job_by_id,
    get_jobs,
    get_jobs_today,
    get_last_scan,
    init_db,
    save_settings,
    toggle_applied,
    toggle_dismissed,
)
from docx_writer import write_cover_letter, write_resume
from models import (
    ApplyResponse,
    AssetResponse,
    DismissResponse,
    Job,
    ProfileContent,
    ScanRequest,
    ScanStatus,
    SourceSetting,
)
from scheduler import daily_scan, is_scan_running, manual_scan, request_cancel, run_daily_scan

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger(__name__)

def _required_api_key(provider: str) -> str | None:
    """Return the API key env var name for a given provider, or None if none is needed."""
    return {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider)


_default_provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
_scoring_provider  = os.getenv("SCORING_PROVIDER",  _default_provider).lower()
_document_provider = os.getenv("DOCUMENT_PROVIDER", _default_provider).lower()

REQUIRED_ENV_VARS = ["ADZUNA_APP_ID", "ADZUNA_APP_KEY"]
for _key in filter(None, {_required_api_key(_scoring_provider), _required_api_key(_document_provider)}):
    REQUIRED_ENV_VARS.append(_key)
ASSETS_PATH = Path(os.getenv("ASSETS_PATH", "/assets"))
# Profile file paths are imported from ai.py so both modules always agree on location.
_RESUME_JSON_PATH = RESUME_PATH.parent / "resume.json"   # legacy fallback for GET

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    init_db()
    ASSETS_PATH.mkdir(parents=True, exist_ok=True)
    scheduler.add_job(run_daily_scan, "cron", hour=6, minute=0, id="daily_scan")
    scheduler.start()
    logger.info("Scheduler started — daily scan at 06:00")
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Job Triage and Apply",
    description="AI-powered job listing scanner and application assistant.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:8080",   # Docker nginx
        "http://127.0.0.1:8080",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@app.get("/api/jobs", response_model=list[Job])
def list_jobs(min_score: int = 0):
    return get_jobs(min_score)


@app.get("/api/jobs/{job_id}", response_model=Job)
def get_job(job_id: str):
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/jobs/{job_id}/dismiss", response_model=DismissResponse)
def dismiss_job(job_id: str):
    if not get_job_by_id(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"dismissed": toggle_dismissed(job_id)}


@app.post("/api/jobs/{job_id}/apply", response_model=ApplyResponse)
def apply_job(job_id: str):
    if not get_job_by_id(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return toggle_applied(job_id)


# ---------------------------------------------------------------------------
# Document generation
# ---------------------------------------------------------------------------

@app.post("/api/jobs/{job_id}/resume", response_model=AssetResponse)
def generate_resume_endpoint(job_id: str):
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    data = generate_resume(job)
    filename = f"resume_{job_id}.docx"
    write_resume(data, str(ASSETS_PATH / filename))
    return {"filename": filename, "url": f"/api/assets/{filename}"}


@app.post("/api/jobs/{job_id}/cover-letter", response_model=AssetResponse)
def generate_cover_letter_endpoint(job_id: str):
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    text = generate_cover_letter(job)
    filename = f"coverletter_{job_id}.docx"
    write_cover_letter(text, str(ASSETS_PATH / filename))
    return {"filename": filename, "url": f"/api/assets/{filename}"}


@app.get("/api/assets/{filename}")
def get_asset(filename: str):
    # Resolve to an absolute path and confirm it stays within ASSETS_PATH.
    # Without this check a crafted filename like "../../data/jobs.db" would
    # escape the assets directory.
    path = (ASSETS_PATH / filename).resolve()
    if not path.is_relative_to(ASSETS_PATH.resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), filename=filename)


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

@app.post("/api/cancel")
def cancel_scan():
    request_cancel()
    return {"ok": True}


@app.post("/api/refresh")
async def refresh(req: ScanRequest, background_tasks: BackgroundTasks):
    if is_scan_running():
        raise HTTPException(status_code=409, detail="A scan is already in progress")
    background_tasks.add_task(manual_scan, req.source, req.keywords, req.location, req.count)
    return {"status": "started"}


@app.get("/api/status", response_model=ScanStatus)
def status():
    last = get_last_scan()
    today = datetime.now(timezone.utc).date().isoformat()
    return {
        "last_scan": last["scanned_at"] if last else None,
        "total_jobs": len(get_jobs()),
        "new_today": get_jobs_today(today),
        "scanning": is_scan_running(),
    }


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.get("/api/settings", response_model=list[SourceSetting])
def get_settings():
    return get_all_settings()


@app.post("/api/settings")
def update_settings(settings: list[SourceSetting]):
    save_settings([s.model_dump() for s in settings])
    return {"ok": True}


# ---------------------------------------------------------------------------
# Profile — resume, writing sample, document instructions
# ---------------------------------------------------------------------------

@app.get("/api/profile/resume")
def get_resume():
    for path in [RESUME_PATH, _RESUME_JSON_PATH]:
        if path.exists():
            return {"content": path.read_text()}
    return {"content": ""}


@app.post("/api/profile/resume")
def save_resume(body: ProfileContent):
    RESUME_PATH.write_text(body.content)
    invalidate_resume_cache()
    return {"ok": True}


@app.get("/api/profile/writing-sample")
def get_writing_sample():
    if WRITING_SAMPLE_PATH.exists():
        return {"content": WRITING_SAMPLE_PATH.read_text()}
    return {"content": ""}


@app.post("/api/profile/writing-sample")
def save_writing_sample(body: ProfileContent):
    WRITING_SAMPLE_PATH.write_text(body.content)
    invalidate_writing_sample_cache()
    return {"ok": True}


@app.get("/api/profile/instructions")
def get_instructions():
    if DOCUMENT_INSTRUCTIONS_PATH.exists():
        return {"content": DOCUMENT_INSTRUCTIONS_PATH.read_text()}
    return {"content": ""}


@app.post("/api/profile/instructions")
def save_instructions(body: ProfileContent):
    DOCUMENT_INSTRUCTIONS_PATH.write_text(body.content)
    invalidate_document_instructions_cache()
    return {"ok": True}
