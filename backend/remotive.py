import re
from datetime import datetime, timezone

import httpx

REMOTIVE_BASE = "https://remotive.com/api/remote-jobs"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


async def fetch_listings(
    keywords: str, location: str, count: int, existing_ids: set[str]
) -> list[dict]:
    params: dict = {"limit": min(count, 100)}
    if keywords:
        params["search"] = keywords

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(REMOTIVE_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()

    new_listings: list[dict] = []
    fetched_at = datetime.now(timezone.utc).isoformat()

    for raw in data.get("jobs", []):
        job_id = f"remotive_{raw['id']}"
        if job_id in existing_ids:
            continue

        new_listings.append({
            "id": job_id,
            "source": "remotive",
            "title": raw.get("title", ""),
            "company": raw.get("company_name", "Unknown"),
            "location": raw.get("candidate_required_location") or "Remote",
            "description": _strip_html(raw.get("description", "")),
            "url": raw.get("url", ""),
            "salary_min": None,
            "salary_max": None,
            "posted_date": raw.get("publication_date", ""),
            "fetched_at": fetched_at,
        })

        if len(new_listings) >= count:
            break

    return new_listings
