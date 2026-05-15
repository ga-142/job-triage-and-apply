import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Job } from "../types";

const API = "/api";

type AssetState = "idle" | "loading" | "done" | "error";

interface AssetResult {
  url: string;
  filename: string;
}

export default function ApplyPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [resumeState, setResumeState] = useState<AssetState>("idle");
  const [resumeResult, setResumeResult] = useState<AssetResult | null>(null);

  const [coverState, setCoverState] = useState<AssetState>("idle");
  const [coverResult, setCoverResult] = useState<AssetResult | null>(null);

  const [applied, setApplied] = useState<string | null>(null);
  const [applyLoading, setApplyLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    fetch(`${API}/jobs/${id}`)
      .then((r) => r.json())
      .then((data: Job) => {
        setJob(data);
        setApplied(data.applied_at);
      })
      .catch(() => setLoadError("Could not load job details."));
  }, [id]);

  const generateAsset = async (
    type: "resume" | "cover-letter",
    setState: (s: AssetState) => void,
    setResult: (r: AssetResult) => void
  ) => {
    setState("loading");
    try {
      const res = await fetch(`${API}/jobs/${id}/${type}`, { method: "POST" });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setResult({ url: data.url, filename: data.filename });
      setState("done");
    } catch {
      setState("error");
    }
  };

  const handleToggleApplied = async () => {
    setApplyLoading(true);
    try {
      const res = await fetch(`${API}/jobs/${id}/apply`, { method: "POST" });
      const data = await res.json();
      setApplied(data.applied_at);
    } catch {
      // silently fail
    } finally {
      setApplyLoading(false);
    }
  };

  if (loadError) {
    return <div className="apply-page"><p className="apply-load-error">{loadError}</p></div>;
  }

  if (!job) {
    return <div className="apply-page"><p className="apply-muted">Loading…</p></div>;
  }

  const appliedDate = applied
    ? new Date(applied).toLocaleDateString(undefined, {
        month: "long",
        day: "numeric",
        year: "numeric",
      })
    : null;

  return (
    <div className="apply-page">
      <div className="apply-card">
        {/* Job header */}
        <div className="apply-job-header">
          <div>
            <h1 className="apply-job-title">{job.title}</h1>
            <p className="apply-job-company">
              {job.company}
              {job.location && (
                <>
                  <span className="job-card-dot">·</span>
                  {job.location}
                </>
              )}
            </p>
          </div>
          <a href={job.url} target="_blank" rel="noopener noreferrer" className="apply-view-link">
            View Posting →
          </a>
        </div>

        <hr className="apply-divider" />

        {/* Document generation */}
        <div className="apply-actions">
          <div className="apply-action-block">
            <h2 className="apply-action-title">Tailored Resume</h2>
            <p className="apply-action-desc">
              Claude rewrites your resume emphasizing skills and experience relevant to this role.
            </p>
            <button
              className="btn-primary"
              style={{ width: "fit-content" }}
              onClick={() => generateAsset("resume", setResumeState, setResumeResult)}
              disabled={resumeState === "loading"}
            >
              {resumeState === "loading"
                ? "Generating…"
                : resumeState === "done"
                ? "Regenerate Resume"
                : "Tailor Resume"}
            </button>
            {resumeState === "done" && resumeResult && (
              <a href={resumeResult.url} download={resumeResult.filename} className="apply-download-link">
                Download {resumeResult.filename}
              </a>
            )}
            {resumeState === "error" && (
              <p className="apply-error-sm">Generation failed. Check backend logs.</p>
            )}
          </div>

          <div className="apply-action-block">
            <h2 className="apply-action-title">Cover Letter</h2>
            <p className="apply-action-desc">
              Claude writes a tailored cover letter addressed to the hiring contact if found in the posting.
            </p>
            <button
              className="btn-primary"
              style={{ width: "fit-content" }}
              onClick={() => generateAsset("cover-letter", setCoverState, setCoverResult)}
              disabled={coverState === "loading"}
            >
              {coverState === "loading"
                ? "Generating…"
                : coverState === "done"
                ? "Regenerate Cover Letter"
                : "Write Cover Letter"}
            </button>
            {coverState === "done" && coverResult && (
              <a href={coverResult.url} download={coverResult.filename} className="apply-download-link">
                Download {coverResult.filename}
              </a>
            )}
            {coverState === "error" && (
              <p className="apply-error-sm">Generation failed. Check backend logs.</p>
            )}
          </div>
        </div>

        <hr className="apply-divider" />

        {/* Applied toggle */}
        <div className="apply-applied-row">
          {appliedDate ? (
            <p className="apply-applied-text">
              Applied on <strong>{appliedDate}</strong>
            </p>
          ) : (
            <p className="apply-muted">Not yet marked as applied.</p>
          )}
          <button
            className={applied ? "btn-ghost" : "btn-teal"}
            onClick={handleToggleApplied}
            disabled={applyLoading}
          >
            {applyLoading ? "…" : applied ? "Unmark Applied" : "Mark as Applied"}
          </button>
        </div>
      </div>
    </div>
  );
}
