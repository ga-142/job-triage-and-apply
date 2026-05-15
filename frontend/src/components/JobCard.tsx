import { Job } from "../types";

interface Props {
  job: Job;
  onDismiss: (id: string) => void;
}

const SOURCE_LABELS: Record<string, string> = {
  adzuna:   "Adzuna",
  remotive: "Remotive",
  remoteok: "Remote OK",
  themuse:  "The Muse",
};

function scoreBadgeClass(score: number): string {
  if (score >= 80) return "score-badge score-badge--high";
  if (score >= 60) return "score-badge score-badge--mid";
  return "score-badge score-badge--low";
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function formatSalary(min: number | null, max: number | null): string | null {
  if (!min && !max) return null;
  const fmt = (n: number) => n >= 1000 ? `$${Math.round(n / 1000)}k` : `$${n}`;
  if (min && max) return `${fmt(min)} – ${fmt(max)}`;
  if (min) return `From ${fmt(min)}`;
  return `Up to ${fmt(max!)}`;
}

export default function JobCard({ job, onDismiss }: Props) {
  const score = job.score ?? 0;
  const salary = formatSalary(job.salary_min, job.salary_max);
  const sourceLabel = SOURCE_LABELS[job.source];

  const cardClass = [
    "job-card",
    job.dismissed  ? "job-card--dismissed" : "",
    job.applied_at ? "job-card--applied"   : "",
  ].filter(Boolean).join(" ");

  return (
    <article className={cardClass}>
      <div className="job-card-top">
        <div className="job-card-meta">
          <h2 className="job-card-title">{job.title}</h2>
          <p className="job-card-company">
            {/* Source pill — which board this came from */}
            {sourceLabel && (
              <>
                <span className="pill pill--source">{sourceLabel}</span>
                <span className="job-card-dot">·</span>
              </>
            )}
            {job.company}
            <span className="job-card-dot">·</span>
            {job.location}
            {salary && (
              <>
                <span className="job-card-dot">·</span>
                <span className="job-card-salary">{salary}</span>
              </>
            )}
            {job.applied_at && (
              <>
                <span className="job-card-dot">·</span>
                <span className="pill pill--applied">Applied</span>
              </>
            )}
          </p>
        </div>

        {/* Score badge — glows in its tier color */}
        <div className={scoreBadgeClass(score)}>{score}</div>
      </div>

      {job.summary && <p className="job-card-summary">{job.summary}</p>}

      {job.match_reasons.length > 0 && (
        <ul className="job-card-bullets">
          {job.match_reasons.map((reason, i) => (
            <li key={i} className="job-card-bullet">{reason}</li>
          ))}
        </ul>
      )}

      <div className="job-card-footer">
        <div className="job-card-footer-left">
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="job-card-view-link"
          >
            View Job →
          </a>
          <span className="job-card-scraped">Scraped {formatDate(job.fetched_at)}</span>
        </div>

        <div className="job-card-actions">
          <button
            className="btn-primary"
            style={{ padding: "5px 14px", fontSize: "12px", boxShadow: "none" }}
            onClick={() => window.open(`/apply/${job.id}`, "_blank", "noopener,noreferrer")}
          >
            Apply
          </button>
          <button
            className="btn-ghost"
            onClick={() => onDismiss(job.id)}
          >
            {job.dismissed ? "Undismiss" : "Dismiss"}
          </button>
        </div>
      </div>
    </article>
  );
}
