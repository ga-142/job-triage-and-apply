# Job Triage and Apply

Personal AI-powered job listing scanner and application assistant. Fetches listings from multiple job boards, scores each one against a resume using an LLM, and generates tailored resumes and cover letters on demand.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLite (stdlib), APScheduler, httpx
- **Frontend**: React 18, TypeScript (strict), Vite — hand-written CSS, no UI framework
- **AI**: Anthropic Claude, OpenAI, or local Ollama — switchable via `LLM_PROVIDER` env var; independently routable via `SCORING_PROVIDER` / `DOCUMENT_PROVIDER`
- **Job sources**: Adzuna, Remotive, Remote OK, The Muse
- **Deployment**: Docker Compose (backend + nginx-fronted frontend + optional Ollama via `--profile ollama`)

## Project Layout

```
job-triage/
├── backend/
│   ├── main.py                   # FastAPI app, lifespan, CORS, all endpoints
│   ├── ai.py                     # LLM dispatch — Anthropic, OpenAI, or Ollama; scoring + document generation
│   ├── scheduler.py              # scan_source(), manual_scan(), daily_scan(), cancel flag
│   ├── database.py               # SQLite init + migrations, all query functions
│   ├── models.py                 # Pydantic request/response models
│   ├── sources.py                # Source registry (REGISTRY dict) and display labels
│   ├── adzuna.py                 # Adzuna API client
│   ├── remotive.py               # Remotive API client
│   ├── remoteok.py               # Remote OK API client
│   ├── themuse.py                # The Muse API client
│   ├── docx_writer.py            # Resume and cover letter DOCX formatting
│   ├── resume.txt                # User's resume — never commit (gitignored)
│   ├── writing_sample.txt        # User's writing sample — never commit (gitignored, optional)
│   ├── document_instructions.txt # User's document style rules — never commit (gitignored, optional)
│   └── tests/                    # pytest test suite
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # Routes: /, /apply/:id, /profile, /settings
│   │   ├── index.css                # Full design system — CSS custom properties, all component classes
│   │   ├── types.ts                 # Job, Status, SourceSetting interfaces
│   │   ├── components/
│   │   │   ├── Header.tsx           # Sticky header, scan command bar, filter controls
│   │   │   └── JobCard.tsx          # Score badge, summary, match reasons, actions
│   │   └── pages/
│   │       ├── Dashboard.tsx        # Job list, polling during scans, filter/sort state
│   │       ├── ApplyPage.tsx        # Document generation + applied tracking
│   │       ├── ProfilePage.tsx      # Resume, writing sample, and document instructions editor
│   │       └── SettingsPage.tsx     # Per-source daily scan configuration
│   ├── Dockerfile                   # Multi-stage: Vite build → nginx
│   └── nginx.conf                   # Proxies /api/* to backend:8000
├── pyproject.toml       # ruff lint config + pytest settings
├── requirements.txt     # Pinned production dependencies
├── requirements-dev.txt # Adds pytest for local development
├── docker-compose.yml
├── .env                 # Secrets — never commit (gitignored)
└── .env.example
```

## Adding a New Job Source

1. Create `backend/<source>.py` implementing `async def fetch_listings(keywords, location, count, existing_ids) -> list[dict]`
2. Register it in `backend/sources.py` — add to both `REGISTRY` and `LABELS`
3. Add a default row to the `defaults` list in `database.py → init_db()`
4. Add the option to the `SOURCES` array in `frontend/src/components/Header.tsx` and `frontend/src/pages/SettingsPage.tsx`

## Database Schema

```sql
-- jobs: one row per listing, inserted after AI analysis
id TEXT PRIMARY KEY   -- namespaced by source: "adzuna_123", "remotive_456"
source TEXT
title, company, location, description, url TEXT
salary_min, salary_max REAL
posted_date, fetched_at, analyzed_at TEXT  -- ISO 8601
score INTEGER          -- 1–100 from LLM
summary TEXT           -- 2-sentence AI summary
match_reasons TEXT     -- JSON array stored as TEXT
dismissed INTEGER      -- 0 or 1
applied_at TEXT        -- ISO 8601 timestamp, NULL if not applied

-- scan_log: one row per scan run
id INTEGER PRIMARY KEY AUTOINCREMENT
scanned_at TEXT, new_jobs_found INTEGER, status TEXT, source TEXT

-- settings: one row per source, seeded with defaults on first run
source TEXT PRIMARY KEY
enabled INTEGER, keywords TEXT, location TEXT, count INTEGER
```

## API Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/health` | Liveness check |
| GET | `/api/jobs?min_score=N` | All jobs sorted by score desc |
| GET | `/api/jobs/{id}` | Single job |
| POST | `/api/jobs/{id}/dismiss` | Toggle dismissed |
| POST | `/api/jobs/{id}/apply` | Toggle applied |
| POST | `/api/jobs/{id}/resume` | Generate tailored resume DOCX |
| POST | `/api/jobs/{id}/cover-letter` | Generate cover letter DOCX |
| GET | `/api/assets/{filename}` | Download generated DOCX |
| POST | `/api/refresh` | Start a manual scan (background task) |
| POST | `/api/cancel` | Cancel the running scan |
| GET | `/api/status` | last_scan, total_jobs, new_today, scanning |
| GET | `/api/settings` | Per-source auto-scan settings |
| POST | `/api/settings` | Save per-source auto-scan settings |
| GET | `/api/profile/resume` | Read resume file content |
| POST | `/api/profile/resume` | Save resume; invalidates in-memory cache |
| GET | `/api/profile/writing-sample` | Read writing sample content |
| POST | `/api/profile/writing-sample` | Save writing sample; invalidates cache |
| GET | `/api/profile/instructions` | Read document instructions content |
| POST | `/api/profile/instructions` | Save document instructions; invalidates cache |

## Key Design Decisions

- **LLM provider switching**: `LLM_PROVIDER=anthropic|openai|ollama` in `.env` — no rebuild needed. `SCORING_PROVIDER` and `DOCUMENT_PROVIDER` override the default independently, so you can run a local model for scoring and a cloud API for document generation. Anthropic uses the SDK with `cache_control: ephemeral` on the system prompt (resume) to cut bulk scan costs; OpenAI uses the OpenAI SDK; Ollama uses httpx directly.
- **Profile file caching**: resume, writing sample, and document instructions are read from disk once and cached in module-level globals. Each `POST /api/profile/*` endpoint calls the corresponding `invalidate_*_cache()` function so changes take effect on the next generation without a restart.
- **Background scanning**: `POST /api/refresh` fires a FastAPI `BackgroundTask`; the sync AI calls run via `asyncio.get_running_loop().run_in_executor()` so the event loop stays free to serve cancel/status requests during a scan.
- **Cancel mechanism**: `_cancel_requested` flag in `scheduler.py` is checked between jobs. The cancel endpoint sets it; `manual_scan` resets it at the start of each run.
- **Deduplication**: `get_existing_ids()` is called once before each scan; source-namespaced IDs (`adzuna_123`) prevent cross-source duplicates.
- **Retry logic**: `analyze_job()` retries up to 3 times with a 2-second delay on any parse or network failure. The raw LLM response is logged at WARNING level on each failure.
- **Path traversal protection**: `/api/assets/{filename}` resolves and validates the path stays within `ASSETS_PATH` before serving.
- **No auth**: single-user local tool.

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest
```
