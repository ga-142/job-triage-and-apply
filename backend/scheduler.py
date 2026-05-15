import asyncio
import logging
from datetime import datetime, timezone

from ai import analyze_job
from database import get_all_settings, get_existing_ids, insert_job, log_scan
from sources import LABELS, REGISTRY

logger = logging.getLogger(__name__)

# Scan state — module-level singletons, fine for a single-user local app.
# Not safe for concurrent multi-user deployments.
_scan_running: bool = False
_cancel_requested: bool = False


def is_scan_running() -> bool:
    return _scan_running


def request_cancel() -> None:
    global _cancel_requested
    _cancel_requested = True


async def scan_source(
    source: str,
    keywords: str,
    location: str,
    count: int,
    existing_ids: set[str],
) -> int:
    """Fetch, analyze, and store jobs from one source. Returns count of new jobs stored."""
    fetcher = REGISTRY.get(source)
    if not fetcher:
        raise ValueError(f"Unknown source: {source!r}")

    listings = await fetcher(keywords, location, count, existing_ids)
    logger.info("%s: %d new listings fetched", LABELS.get(source, source), len(listings))

    loop = asyncio.get_running_loop()
    new_count = 0
    for listing in listings:
        if _cancel_requested:
            logger.info("Scan cancelled — stopped after %d new jobs", new_count)
            break
        try:
            # Run sync AI call in a thread pool so the event loop stays free
            # to process cancel/status requests during analysis.
            analysis = await loop.run_in_executor(None, analyze_job, listing)
            insert_job({
                **listing,
                "score": analysis["score"],
                "summary": analysis["summary"],
                "match_reasons": analysis["match_reasons"],
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            })
            # Add to the in-memory set so subsequent sources in the same run
            # don't re-fetch a job that was just inserted.
            existing_ids.add(listing["id"])
            new_count += 1
            logger.info(
                "Stored: %s @ %s — score %d",
                listing["title"],
                listing["company"],
                analysis["score"],
            )
        except Exception:
            logger.exception("Failed to analyze job %s", listing.get("id"))

    return new_count


async def manual_scan(source: str, keywords: str, location: str, count: int) -> int:
    """One-off scan triggered from the UI. Runs as a background task."""
    global _scan_running, _cancel_requested
    _scan_running = True
    _cancel_requested = False
    scanned_at = datetime.now(timezone.utc).isoformat()
    existing_ids = get_existing_ids()
    try:
        new_count = await scan_source(source, keywords, location, count, existing_ids)
        log_scan(scanned_at, new_count, "success", source)
        logger.info("Manual scan complete. %d new jobs stored.", new_count)
        return new_count
    except Exception:
        log_scan(scanned_at, 0, "error", source)
        logger.exception("Manual scan failed for source %s", source)
    finally:
        _scan_running = False


async def daily_scan() -> int:
    """06:00 auto-scan — runs all enabled sources using their saved settings."""
    global _scan_running
    settings = get_all_settings()
    enabled = [s for s in settings if s["enabled"]]

    if not enabled:
        logger.info("Daily scan: no sources enabled, skipping")
        return 0

    _scan_running = True
    scanned_at = datetime.now(timezone.utc).isoformat()
    existing_ids = get_existing_ids()
    total_new = 0

    try:
        for cfg in enabled:
            source = cfg["source"]
            logger.info("Daily scan: starting source %s", LABELS.get(source, source))
            try:
                n = await scan_source(
                    source, cfg["keywords"], cfg["location"], cfg["count"], existing_ids
                )
                log_scan(scanned_at, n, "success", source)
                total_new += n
            except Exception:
                log_scan(scanned_at, 0, "error", source)
                logger.exception("Daily scan failed for source %s", source)
    finally:
        _scan_running = False

    logger.info("Daily scan complete. %d total new jobs stored.", total_new)
    return total_new


# APScheduler runs synchronous jobs. This wrapper lets the scheduler invoke
# the async daily_scan without requiring an already-running event loop.
def run_daily_scan():
    asyncio.run(daily_scan())
