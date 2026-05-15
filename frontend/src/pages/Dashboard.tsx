import { useCallback, useEffect, useState } from "react";
import Header from "../components/Header";
import JobCard from "../components/JobCard";
import { Job, Status } from "../types";

const API = "/api";

type SortBy = "score" | "date";
type DateFilter = "all" | "today" | "7d" | "30d";

function cutoff(filter: DateFilter): Date | null {
  const now = new Date();
  if (filter === "today") return new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (filter === "7d") return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  if (filter === "30d") return new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  return null;
}

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [minScore, setMinScore] = useState(60);
  const [showDismissed, setShowDismissed] = useState(false);
  const [showApplied, setShowApplied] = useState(false);
  const [sortBy, setSortBy] = useState<SortBy>("score");
  const [dateFilter, setDateFilter] = useState<DateFilter>("all");
  const [scanSource, setScanSource] = useState("adzuna");
  const [scanKeywords, setScanKeywords] = useState("");
  const [scanLocation, setScanLocation] = useState("");
  const [scanCount, setScanCount] = useState(50);
  const [error, setError] = useState<string | null>(null);

  // Scanning state is authoritative from the backend via status.scanning.
  // We optimistically flip it true on click so the progress bar appears instantly.
  const scanning = status?.scanning ?? false;

  const loadJobs = useCallback(async () => {
    try {
      const [jobsRes, statusRes] = await Promise.all([
        fetch(`${API}/jobs?min_score=${minScore}`),
        fetch(`${API}/status`),
      ]);
      setJobs(await jobsRes.json());
      setStatus(await statusRes.json());
      setError(null);
    } catch {
      setError("Could not connect to backend. Is it running?");
    }
  }, [minScore]);

  // Initial load
  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  // Poll every 2.5 s while the backend reports a scan in progress.
  // This keeps the job list live and catches completion after page refresh.
  useEffect(() => {
    if (!scanning) return;
    const id = setInterval(loadJobs, 2500);
    return () => clearInterval(id);
  }, [scanning, loadJobs]);

  const handleRefresh = async () => {
    setError(null);
    // Optimistically mark scanning so the progress bar appears immediately.
    setStatus((prev: Status | null) => prev ? { ...prev, scanning: true } : prev);
    try {
      const res = await fetch(`${API}/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: scanSource,
          keywords: scanKeywords,
          location: scanLocation,
          count: scanCount,
        }),
      });
      if (res.status === 409) {
        // Already running — no-op, polling will show it
        return;
      }
      if (!res.ok) throw new Error();
    } catch {
      setError("Scan failed to start. Check backend logs.");
      setStatus((prev: Status | null) => prev ? { ...prev, scanning: false } : prev);
    }
  };

  const handleCancel = () => {
    // Optimistically clear the scan bar immediately for instant feedback.
    // The backend finishes the current job then stops; the next poll confirms it.
    setStatus((prev: Status | null) => prev ? { ...prev, scanning: false } : prev);
    fetch(`${API}/cancel`, { method: "POST" }).catch(() => {});
  };

  const handleDismiss = async (id: string) => {
    try {
      const res = await fetch(`${API}/jobs/${id}/dismiss`, { method: "POST" });
      const { dismissed } = await res.json();
      setJobs((prev: Job[]) =>
        prev.map((j) => (j.id === id ? { ...j, dismissed } : j))
      );
    } catch {
      setError("Failed to update job.");
    }
  };

  const since = cutoff(dateFilter);

  const visible = jobs
    .filter((j: Job) => {
      if (!showDismissed && j.dismissed) return false;
      if (!showApplied && j.applied_at) return false;
      if (since && new Date(j.fetched_at) < since) return false;
      return true;
    })
    .sort((a: Job, b: Job) => {
      if (sortBy === "date") {
        return new Date(b.fetched_at).getTime() - new Date(a.fetched_at).getTime();
      }
      return (b.score ?? 0) - (a.score ?? 0);
    });

  return (
    <div>
      <Header
        status={status}
        minScore={minScore}
        onMinScoreChange={setMinScore}
        onRefresh={handleRefresh}
        onCancel={handleCancel}
        refreshing={scanning}
        showDismissed={showDismissed}
        onShowDismissedChange={setShowDismissed}
        showApplied={showApplied}
        onShowAppliedChange={setShowApplied}
        sortBy={sortBy}
        onSortByChange={setSortBy}
        dateFilter={dateFilter}
        onDateFilterChange={setDateFilter}
        scanSource={scanSource}
        onScanSourceChange={setScanSource}
        scanKeywords={scanKeywords}
        onScanKeywordsChange={setScanKeywords}
        scanLocation={scanLocation}
        onScanLocationChange={setScanLocation}
        scanCount={scanCount}
        onScanCountChange={setScanCount}
      />

      {error && <div className="dashboard-error">{error}</div>}

      {!error && visible.length === 0 && (
        <div className="dashboard-empty">
          No jobs found yet. Click <strong>Scan Now</strong> to fetch and analyze listings.
        </div>
      )}

      {visible.map((job: Job) => (
        <JobCard key={job.id} job={job} onDismiss={handleDismiss} />
      ))}
    </div>
  );
}
