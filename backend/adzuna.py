import math
import os
from datetime import datetime, timezone

import httpx

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs/us/search"
RESULTS_PER_PAGE = 50
MAX_PAGES = 4


def _parse_job(raw: dict) -> dict:
    loc = raw.get("location", {})
    location_str = ", ".join(loc.get("area", [])) if loc else "Unknown"
    salary_min = raw.get("salary_min")
    salary_max = raw.get("salary_max")

    return {
        "id": f"adzuna_{raw['id']}",
        "source": "adzuna",
        "title": raw.get("title", ""),
        "company": raw.get("company", {}).get("display_name", "Unknown"),
        "location": location_str,
        "description": raw.get("description", ""),
        "url": raw.get("redirect_url", ""),
        "salary_min": float(salary_min) if salary_min else None,
        "salary_max": float(salary_max) if salary_max else None,
        "posted_date": raw.get("created", ""),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


async def fetch_listings(
    keywords: str, location: str, count: int, existing_ids: set[str]
) -> list[dict]:
    app_id = os.environ["ADZUNA_APP_ID"]
    app_key = os.environ["ADZUNA_APP_KEY"]

    pages = min(math.ceil(count / RESULTS_PER_PAGE), MAX_PAGES)
    new_listings: list[dict] = []

    async with httpx.AsyncClient(timeout=30) as client:
        for page in range(1, pages + 1):
            params: dict = {
                "app_id": app_id,
                "app_key": app_key,
                "what": keywords,
                "results_per_page": RESULTS_PER_PAGE,
                "content-type": "application/json",
            }
            # Adzuna's `where` field is geographic — omit it entirely when
            # blank rather than passing an empty string (which returns 0 results).
            if location:
                params["where"] = location

            resp = await client.get(f"{ADZUNA_BASE}/{page}", params=params)
            resp.raise_for_status()

            results = resp.json().get("results", [])
            if not results:
                break

            for raw in results:
                job_id = f"adzuna_{raw.get('id')}"
                if raw.get("id") and job_id not in existing_ids:
                    new_listings.append(_parse_job(raw))
                if len(new_listings) >= count:
                    break

            if len(new_listings) >= count:
                break

    return new_listings[:count]
