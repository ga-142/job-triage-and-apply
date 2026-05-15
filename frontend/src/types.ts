export interface Job {
  id: string;
  source: string;
  title: string;
  company: string;
  location: string;
  description: string;
  url: string;
  salary_min: number | null;
  salary_max: number | null;
  posted_date: string | null;
  fetched_at: string;
  score: number | null;
  summary: string | null;
  match_reasons: string[];
  analyzed_at: string | null;
  dismissed: boolean;
  applied_at: string | null;
}

export interface Status {
  last_scan: string | null;
  total_jobs: number;
  new_today: number;
  scanning: boolean;
}

export interface SourceSetting {
  source: string;
  enabled: boolean;
  keywords: string;
  location: string;
  count: number;
}
