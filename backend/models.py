from pydantic import BaseModel


class Job(BaseModel):
    id: str
    source: str = "adzuna"
    title: str
    company: str
    location: str
    description: str
    url: str
    salary_min: float | None = None
    salary_max: float | None = None
    posted_date: str | None = None
    fetched_at: str
    score: int | None = None
    summary: str | None = None
    match_reasons: list[str] = []
    analyzed_at: str | None = None
    dismissed: bool = False
    applied_at: str | None = None


class ScanStatus(BaseModel):
    last_scan: str | None
    total_jobs: int
    new_today: int
    scanning: bool = False


class DismissResponse(BaseModel):
    dismissed: bool


class ApplyResponse(BaseModel):
    applied_at: str | None


class AssetResponse(BaseModel):
    filename: str
    url: str


class ScanRequest(BaseModel):
    source: str
    keywords: str = ""
    location: str = ""
    count: int = 50


class SourceSetting(BaseModel):
    source: str
    enabled: bool
    keywords: str = ""
    location: str = ""
    count: int = 50


class ProfileContent(BaseModel):
    content: str
