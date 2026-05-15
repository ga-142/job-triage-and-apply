# Job Triage and Apply

A personal AI-powered job listing scanner and application assistant. Pulls listings from multiple job boards, scores each one against your resume, and generates tailored resumes and cover letters — all running locally.

The documents it produces actually sound like you. Feed it a writing sample and a set of style rules ("no buzzwords, no inflated claims, write like an engineer not a recruiter") and the AI follows them. Point it at a cheap local model for bulk scoring and a stronger cloud API for the documents that matter. Everything is configurable without touching code.

## Features

### Scanning and scoring
- **Multi-source scanning** — Adzuna, Remotive, Remote OK, and The Muse in one dashboard
- **AI scoring** — every listing is scored 1–100 against your resume with a plain-English explanation of why it does or doesn't fit
- **Background scanning** — scans run in the background so you can keep browsing; progress bar with cancel button
- **Configurable daily auto-scan** — set keywords, location, and result count per source from the Settings page
- **Deduplication** — listings already in the database are never re-analyzed

### Document generation
- **Tailored documents** — generate a role-specific resume and cover letter (DOCX) for any listing with one click
- **Writing sample** — paste a few paragraphs of your own writing and the AI mirrors your tone across every document it generates
- **Document instructions** — ban buzzwords, enforce a style, set rules the AI must follow: *"no 'passionate', no inflated metrics, write like an engineer explaining real work to another engineer"*
- **Sounds like you, not ChatGPT** — the combination of writing sample + explicit instructions produces output that's actually usable without a full rewrite

### AI and infrastructure
- **Three AI providers** — Anthropic Claude, OpenAI, or a local Ollama model; swap with a single env var, no rebuild required
- **Model routing** — `SCORING_PROVIDER` and `DOCUMENT_PROVIDER` are configured independently. Run a fast free local model for bulk scoring and reserve the stronger cloud API for the cover letters you actually send
- **Profile page** — edit your resume, writing sample, and document instructions directly in the UI; changes take effect on the next generation without a restart

### Job management
- **Dismiss / undismiss** — gray out listings you're not interested in
- **Applied tracking** — mark jobs as applied; applied listings get a teal border in the dashboard
- **Filtering and sorting** — by score, date scraped, and time window
- **Dark synthwave UI** — because why not

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, SQLite, APScheduler, httpx |
| Frontend | React 18, TypeScript, Vite — hand-written CSS, no UI framework |
| AI | Anthropic Claude, OpenAI, **or** local Ollama — switchable via env vars |
| Job sources | Adzuna, Remotive, Remote OK, The Muse |
| Deployment | Docker Compose |

---

## Prerequisites

- [Docker + Docker Compose](https://docs.docker.com/get-docker/)
- [Adzuna API credentials](https://developer.adzuna.com) (free — 250 req/day)
- **One of:**
  - [Anthropic API key](https://console.anthropic.com) — easiest to get started
  - [OpenAI API key](https://platform.openai.com/api-keys)
  - [Ollama](https://ollama.com) running locally — free after model download

---

## Setup

### 1. Clone and configure

```bash
git clone <your-repo-url>
cd job-triage
cp .env.example .env
```

### 2. Edit `.env`

**Using Anthropic (default):**

```env
ADZUNA_APP_ID=your_app_id
ADZUNA_APP_KEY=your_app_key

LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_key
ANTHROPIC_MODEL=claude-sonnet-4-6
```

**Using OpenAI:**

```env
ADZUNA_APP_ID=your_app_id
ADZUNA_APP_KEY=your_app_key

LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o
```

**Using Ollama:**

```env
ADZUNA_APP_ID=your_app_id
ADZUNA_APP_KEY=your_app_key

LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b
```

> `host.docker.internal` resolves to your host machine from inside the Docker container. If you're running Ollama inside Docker Compose instead, set `OLLAMA_BASE_URL=http://ollama:11434`.

**Split routing — local model for scoring, cloud API for documents:**

You can route the two tasks to different providers independently. Job scoring runs on every listing and should be fast; resume and cover letter generation runs rarely and benefits from a stronger model.

```env
# Use a local model for scoring (fast, free, runs on every job)
SCORING_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b

# Use a cloud API for documents (higher quality for things you actually send)
DOCUMENT_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_key
ANTHROPIC_MODEL=claude-sonnet-4-6
```

`SCORING_PROVIDER` and `DOCUMENT_PROVIDER` both fall back to `LLM_PROVIDER`, so a basic `.env` with just `LLM_PROVIDER` works without changes.

### 3. Add your resume

Create `backend/resume.txt` with your resume as plain text. The full content is injected into the AI system prompt on every scan and document generation — include anything relevant to the roles you're targeting.

Plain text is the recommended format, but JSON also works if you prefer structured data. See `backend/resume.example.txt` for a template.

Alternatively, skip this step and paste your resume directly in the **Profile** page after the app starts.

> The file is gitignored and never committed.

### 4. Add a writing sample and document instructions (optional)

**Writing sample** (`backend/writing_sample.txt`): a few paragraphs of your own writing — a past cover letter, a bio, anything that sounds like you. The AI mirrors this tone when generating resumes and cover letters. The sample is capped at 400 words before being sent to the model (configurable via `WRITING_SAMPLE_MAX_WORDS`).

**Document instructions** (`backend/document_instructions.txt`): rules the AI must follow. Use this to ban buzzwords, set tone, or enforce style preferences:

```
- Do not use words like "passionate", "ninja", or "synergy"
- Keep the tone direct and technically grounded
- Never start a bullet point with "I"
```

Both files are gitignored. You can also set them from the **Profile** page in the UI after the app starts.

### 5. Start with Docker Compose

```bash
docker compose up --build -d
```

Open **[http://localhost:8080](http://localhost:8080)**.

The SQLite database and generated DOCX files are persisted across restarts — the database in a named Docker volume (`db_data`), documents in `./assets/` on your host.

---

## Using Ollama

### Option A — Ollama running on your host (recommended)

Keep Ollama running normally on your machine. Set in `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b
```

Pull your model on the host before starting the stack:

```bash
ollama pull qwen2.5:7b
```

### Option B — Ollama in Docker Compose

The `ollama` service in `docker-compose.yml` is disabled by default. Enable it with the `ollama` profile:

```bash
docker compose --profile ollama up --build -d
# Pull a model — models persist in the ollama_data volume
docker compose exec ollama ollama pull qwen2.5:7b
```

Set in `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b
```

### Model recommendations

Choose based on your GPU VRAM:

| VRAM | Recommended model | Notes |
|------|-------------------|-------|
| 4–5 GB | `mistral:7b-instruct` | Reliable JSON output |
| 5–6 GB | `qwen2.5:7b` | Best quality at this size for structured tasks |
| 8 GB | `llama3.1:8b` | Strong general quality |
| 12 GB | `qwen2.5:14b` | Near-API quality for scoring and writing |
| 24 GB | `llama3.1:70b` | Excellent across all tasks |

Browse all available models at [ollama.com/library](https://ollama.com/library).

Switching models requires no rebuild — update `OLLAMA_MODEL` in `.env` and restart:

```bash
docker compose restart backend
```

---

## Running Your First Scan

1. Open [http://localhost:8080](http://localhost:8080)
2. In the command bar at the top, select a source, enter keywords, and choose a result count
3. Click **Scan Now** — the progress bar will appear while the scan runs in the background
4. Jobs appear as they are analyzed; you can browse and dismiss while the scan continues
5. Click **Cancel** at any time to stop mid-scan — jobs stored so far are kept

---

## Daily Auto-Scan

The app runs a scan automatically at **06:00 local time** using settings you configure per source.

Go to **Settings** (top-right link) to:
- Enable or disable each job source
- Set keywords, location (Adzuna only), and result count per source
- Click **Save Settings** — takes effect on the next scheduled run

---

## Profile Page

Click **Profile** (top-right link) to manage the inputs used for scoring and document generation:

- **Resume** — paste your resume as plain text (or JSON). Saved immediately to `backend/resume.txt`; no restart needed.
- **Writing Sample** — a few paragraphs of your own writing. The AI mirrors your tone in generated documents.
- **Document Instructions** — rules the AI must follow: banned words, tone requirements, style preferences. Each section has its own Save button and takes effect on the next generation.

---

## Apply Workflow

Click **Apply** on any job card to open the apply page for that listing:

- **Tailor Resume** — the AI rewrites your resume emphasizing experience and skills relevant to this specific role. Downloads as a formatted DOCX.
- **Write Cover Letter** — the AI writes a professional cover letter addressed to the hiring contact if one is found in the posting. Downloads as DOCX.
- **Mark as Applied** — toggle to track which jobs you've applied to. Applied jobs show a teal border in the dashboard.

---

## Job Management

| Action | How |
|---|---|
| Dismiss a listing | Click **Dismiss** on the card — grays it out |
| Undismiss | Click **Undismiss** on a dismissed card |
| Show dismissed | Toggle **Show Dismissed** in the filter bar |
| Mark as applied | Open the Apply page and click **Mark as Applied** |
| Show applied | Toggle **Show Applied** in the filter bar |

---

## Filtering and Sorting

The header filter bar lets you:
- **Min score slider** — hide listings below a threshold
- **Sort** — by AI score (default) or date scraped
- **Scraped** — show all time, today, last 7 days, or last 30 days

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/jobs?min_score=N` | All jobs sorted by score desc |
| `GET` | `/api/jobs/{id}` | Single job |
| `POST` | `/api/jobs/{id}/dismiss` | Toggle dismissed state |
| `POST` | `/api/jobs/{id}/apply` | Toggle applied state |
| `POST` | `/api/jobs/{id}/resume` | Generate tailored resume DOCX |
| `POST` | `/api/jobs/{id}/cover-letter` | Generate cover letter DOCX |
| `GET` | `/api/assets/{filename}` | Download generated DOCX |
| `POST` | `/api/refresh` | Start a scan (background task) |
| `POST` | `/api/cancel` | Cancel the running scan |
| `GET` | `/api/status` | Last scan time, total jobs, new today, scanning state |
| `GET` | `/api/settings` | Per-source auto-scan settings |
| `POST` | `/api/settings` | Save per-source auto-scan settings |
| `GET` | `/api/profile/resume` | Read resume content |
| `POST` | `/api/profile/resume` | Save resume content |
| `GET` | `/api/profile/writing-sample` | Read writing sample |
| `POST` | `/api/profile/writing-sample` | Save writing sample |
| `GET` | `/api/profile/instructions` | Read document instructions |
| `POST` | `/api/profile/instructions` | Save document instructions |

Interactive API docs available at [http://localhost:8000/docs](http://localhost:8000/docs) when running locally.

---

## Project Structure

```
job-triage/
├── backend/
│   ├── main.py                  # FastAPI app, lifespan, CORS, all endpoints
│   ├── ai.py                    # LLM dispatch — Anthropic, OpenAI, or Ollama
│   ├── scheduler.py             # Background scan logic, cancel flag, APScheduler
│   ├── database.py              # SQLite init, migrations, all query functions
│   ├── models.py                # Pydantic models
│   ├── sources.py               # Source registry and labels
│   ├── adzuna.py                # Adzuna API client
│   ├── remotive.py              # Remotive API client
│   ├── remoteok.py              # Remote OK API client
│   ├── themuse.py               # The Muse API client
│   ├── docx_writer.py           # Resume and cover letter DOCX formatting
│   ├── resume.txt               # Your resume (not committed)
│   ├── writing_sample.txt       # Your writing sample (not committed, optional)
│   ├── document_instructions.txt# Your document style rules (not committed, optional)
│   ├── resume.example.txt       # Resume template
│   └── tests/                   # pytest test suite
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── index.css            # Design system — CSS variables, all component classes
│   │   ├── types.ts
│   │   ├── components/
│   │   │   ├── Header.tsx       # Sticky header, command bar, filter controls
│   │   │   └── JobCard.tsx      # Score badge, summary, match reasons, actions
│   │   └── pages/
│   │       ├── Dashboard.tsx    # Main job list with live polling during scans
│   │       ├── ApplyPage.tsx    # Document generation and applied tracking
│   │       ├── ProfilePage.tsx  # Resume, writing sample, and document instructions
│   │       └── SettingsPage.tsx # Per-source daily scan configuration
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── assets/              # Generated DOCX files (host bind mount, gitignored)
├── pyproject.toml       # ruff lint config + pytest settings
├── requirements.txt     # Pinned production dependencies
├── requirements-dev.txt # Adds pytest for local development
├── docker-compose.yml
├── .env                 # Your credentials (never commit)
└── .env.example
```

---

## Local Development (without Docker)

```bash
# Backend
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload
# http://localhost:8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
# http://localhost:5173
```

---

## Testing

### Backend

```bash
pip install -r requirements-dev.txt
pytest
```

Tests cover AI response parsing, retry logic, and all database operations. No real API calls are made — the LLM is mocked.

### Frontend (lint)

ESLint runs against the host source files via a throwaway Docker container — no local Node required:

```bash
docker run --rm -v $(pwd)/frontend:/app -w /app node:20-slim npm run lint
```

---

## Debugging

Set `LOG_LEVEL=DEBUG` in `.env` and restart the backend to print the full LLM prompt (including your resume, writing sample, and instructions) to the logs:

```bash
docker compose restart backend
docker compose logs -f backend
```

Remove or reset to `LOG_LEVEL=INFO` when done — at DEBUG level the full resume JSON is logged on every scoring call.

---

## Notes

- **No auth** — single-user local tool, no login required.
- **Prompt caching** — when using Anthropic, the resume system prompt is cached for ~5 minutes, so bulk scans cost significantly less than individual API calls.
- **Deduplication** — job IDs are namespaced by source (`adzuna_123`, `remotive_456`), so the same role appearing on multiple boards won't be double-analyzed.
- **Cancel safety** — cancelling a scan lets the current job finish analysis before stopping; all results stored up to that point are kept.
- **Storage** — SQLite database in a Docker named volume, DOCX files in `./assets/` on your host. No external services required.
- **Live profile edits** — changes saved via the Profile page take effect immediately; the in-memory cache is invalidated on each save without a restart.
