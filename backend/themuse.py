import math
import re
from datetime import datetime, timezone

import httpx

THEMUSE_BASE = "https://www.themuse.com/api/public/jobs"
RESULTS_PER_PAGE = 20

# The Muse public API doesn't support free-text search — it uses predefined
# category values. We fetch Engineering jobs and filter by keyword in the
# title client-side, which is imperfect but works without an API key.
CATEGORY = "Engineering"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


async def fetch_listings(
    keywords: str, location: str, count: int, existing_ids: set[str]
) -> list[dict]:
    pages_needed = math.ceil(count / RESULTS_PER_PAGE)
    kw_terms = [k.lower() for k in keywords.split()] if keywords else []
    new_listings: list[dict] = []
    fetched_at = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient(timeout=30) as client:
        for page in range(pages_needed * 3):  # over-fetch to account for keyword filtering
            params: dict = {
                "category": CATEGORY,
                "page": page,
                "descended": "true",
            }
            if location:
                params["location"] = location

            resp = await client.get(THEMUSE_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()

            page_results = data.get("results", [])
            if not page_results:
                break

            for raw in page_results:
                title = raw.get("name", "")

                # Filter by keyword presence in title when keywords were provided.
                if kw_terms and not any(k in title.lower() for k in kw_terms):
                    continue

                job_id = f"themuse_{raw['id']}"
                if job_id in existing_ids:
                    continue

                locations = raw.get("locations", [])
                loc_str = ", ".join(l["name"] for l in locations) if locations else "Remote"

                new_listings.append({
                    "id": job_id,
                    "source": "themuse",
                    "title": title,
                    "company": raw.get("company", {}).get("name", "Unknown"),
                    "location": loc_str,
                    "description": _strip_html(raw.get("contents", "")),
                    "url": raw.get("refs", {}).get("landing_page", ""),
                    "salary_min": None,
                    "salary_max": None,
                    "posted_date": raw.get("publication_date", ""),
                    "fetched_at": fetched_at,
                })

                if len(new_listings) >= count:
                    break

            if len(new_listings) >= count:
                break

            if page >= data.get("page_count", 1) - 1:
                break

    return new_listings[:count]
