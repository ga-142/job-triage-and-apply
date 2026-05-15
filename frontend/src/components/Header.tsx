import { Link } from "react-router-dom";
import { Status } from "../types";

type SortBy = "score" | "date";
type DateFilter = "all" | "today" | "7d" | "30d";

const SOURCES = [
  { value: "adzuna",   label: "Adzuna"    },
  { value: "remotive", label: "Remotive"  },
  { value: "remoteok", label: "Remote OK" },
  { value: "themuse",  label: "The Muse"  },
];

const SOURCE_LABELS: Record<string, string> = Object.fromEntries(
  SOURCES.map((s) => [s.value, s.label])
);

const COUNT_OPTIONS = [10, 25, 50, 100, 200];

interface Props {
  status: Status | null;
  minScore: number;
  onMinScoreChange: (v: number) => void;
  onRefresh: () => void;
  onCancel: () => void;
  refreshing: boolean;
  showDismissed: boolean;
  onShowDismissedChange: (v: boolean) => void;
  showApplied: boolean;
  onShowAppliedChange: (v: boolean) => void;
  sortBy: SortBy;
  onSortByChange: (v: SortBy) => void;
  dateFilter: DateFilter;
  onDateFilterChange: (v: DateFilter) => void;
  scanSource: string;
  onScanSourceChange: (v: string) => void;
  scanKeywords: string;
  onScanKeywordsChange: (v: string) => void;
  scanLocation: string;
  onScanLocationChange: (v: string) => void;
  scanCount: number;
  onScanCountChange: (v: number) => void;
}

function formatDate(iso: string | null): string {
  if (!iso) return "Never";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Header({
  status,
  minScore,
  onMinScoreChange,
  onRefresh,
  onCancel,
  refreshing,
  showDismissed,
  onShowDismissedChange,
  showApplied,
  onShowAppliedChange,
  sortBy,
  onSortByChange,
  dateFilter,
  onDateFilterChange,
  scanSource,
  onScanSourceChange,
  scanKeywords,
  onScanKeywordsChange,
  scanLocation,
  onScanLocationChange,
  scanCount,
  onScanCountChange,
}: Props) {
  return (
    <header className="header-root">
      {/* Title row */}
      <div className="header-top">
        <div>
          <h1 className="header-title">Job Triage and Apply</h1>
          <p className="header-sub">
            {status
              ? `${status.total_jobs} jobs · ${status.new_today} new today · Last scan: ${formatDate(status.last_scan)}`
              : "Connecting..."}
          </p>
        </div>
        <div className="header-nav">
          <Link to="/profile" className="header-settings-link">Profile</Link>
          <Link to="/settings" className="header-settings-link">Settings</Link>
        </div>
      </div>

      {/* Command bar — swaps to progress bar while scanning */}
      {refreshing ? (
        <div className="header-scan-bar">
          <div className="scan-progress-wrap">
            <span className="scan-status-text">
              Scanning {SOURCE_LABELS[scanSource] ?? scanSource}…
            </span>
            <div className="scan-progress-bar">
              <div className="scan-progress-fill" />
            </div>
          </div>
          <button className="btn-cancel" onClick={onCancel}>Cancel</button>
        </div>
      ) : (
        <div className="header-scan-bar">
          <select
            className="field-select"
            value={scanSource}
            onChange={(e) => onScanSourceChange(e.target.value)}
          >
            {SOURCES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>

          <input
            type="text"
            className="field-input"
            style={{ width: "180px" }}
            value={scanKeywords}
            onChange={(e) => onScanKeywordsChange(e.target.value)}
            placeholder="Keywords"
          />

          {/* Location only shown for Adzuna — other sources are remote-only or filter differently */}
          {scanSource === "adzuna" && (
            <input
              type="text"
              className="field-input"
              style={{ width: "150px" }}
              value={scanLocation}
              onChange={(e) => onScanLocationChange(e.target.value)}
              placeholder="Location"
            />
          )}

          <select
            className="field-select"
            value={scanCount}
            onChange={(e) => onScanCountChange(Number(e.target.value))}
          >
            {COUNT_OPTIONS.map((n) => (
              <option key={n} value={n}>{n} results</option>
            ))}
          </select>

          <button className="btn-primary" onClick={onRefresh}>
            Scan Now
          </button>
        </div>
      )}

      {/* Filter controls */}
      <div className="header-controls">
        <div className="header-filter">
          <label className="header-label">
            Min score: <strong>{minScore}</strong>
          </label>
          <input
            type="range"
            className="header-slider"
            min={0}
            max={100}
            step={5}
            value={minScore}
            onChange={(e) => onMinScoreChange(Number(e.target.value))}
          />
        </div>

        <div className="header-filter">
          <label className="header-label">Sort:</label>
          <select
            className="field-select"
            value={sortBy}
            onChange={(e) => onSortByChange(e.target.value as SortBy)}
          >
            <option value="score">Score</option>
            <option value="date">Date Scraped</option>
          </select>
        </div>

        <div className="header-filter">
          <label className="header-label">Scraped:</label>
          <select
            className="field-select"
            value={dateFilter}
            onChange={(e) => onDateFilterChange(e.target.value as DateFilter)}
          >
            <option value="all">All time</option>
            <option value="today">Today</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
          </select>
        </div>

        <div className="header-checkboxes">
          <label className="header-check-label">
            <input
              type="checkbox"
              checked={showDismissed}
              onChange={(e) => onShowDismissedChange(e.target.checked)}
            />
            Show Dismissed
          </label>
          <label className="header-check-label">
            <input
              type="checkbox"
              checked={showApplied}
              onChange={(e) => onShowAppliedChange(e.target.checked)}
            />
            Show Applied
          </label>
        </div>
      </div>
    </header>
  );
}
