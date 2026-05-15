from typing import Awaitable, Callable

from adzuna import fetch_listings as _adzuna
from remotive import fetch_listings as _remotive
from remoteok import fetch_listings as _remoteok
from themuse import fetch_listings as _themuse

# Type alias for the shared fetcher interface all source modules implement.
FetchFn = Callable[[str, str, int, set[str]], Awaitable[list[dict]]]

REGISTRY: dict[str, FetchFn] = {
    "adzuna": _adzuna,
    "remotive": _remotive,
    "remoteok": _remoteok,
    "themuse": _themuse,
}

# Human-readable labels used in the UI and logs.
LABELS: dict[str, str] = {
    "adzuna": "Adzuna",
    "remotive": "Remotive",
    "remoteok": "Remote OK",
    "themuse": "The Muse",
}
