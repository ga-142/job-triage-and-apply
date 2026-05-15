import re
from datetime import datetime, timezone

import httpx

REMOTEOK_BASE = "https://remoteok.com/api"

# Remote OK requires a descriptive User-Agent or they return 403.
HEADERS = {"User-Agent": "job-triage/1.0"}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


async def fetch_listings(
    keywords: str, location: str, count: int, existing_ids: set[str]
) -> list[dict]:
    params: dict = {}
    if keywords:
        # Remote OK filters by tag — use the first meaningful keyword as the tag.
        params["tag"] = keywords.split()[0].lower()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(REMOTEOK_BASE, params=params, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()

    # The API always prepends a legal/metadata object as the first element.
    jobs = [item for item in data if isinstance(item, dict) and "position" in item]

    new_listings: list[dict] = []
    fetched_at = datetime.now(timezone.utc).isoformat()

    for raw in jobs:
        job_id = f"remoteok_{raw['id']}"
        if job_id in existing_ids:
            continue

        salary_min = raw.get("salary_min")
        salary_max = raw.get("salary_max")

        new_listings.append({
            "id": job_id,
            "source": "remoteok",
            "title": raw.get("position", ""),
            "company": raw.get("company", "Unknown"),
            "location": raw.get("location") or "Remote",
            "description": _strip_html(raw.get("description", "")),
            "url": raw.get("url", ""),
            "salary_min": float(salary_min) if salary_min else None,
            "salary_max": float(salary_max) if salary_max else None,
            "posted_date": raw.get("date", ""),
            "fetched_at": fetched_at,
        })

        if len(new_listings) >= count:
            break

    return new_listings
