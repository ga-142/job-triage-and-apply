import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { SourceSetting } from "../types";

const API = "/api";

const SOURCE_LABELS: Record<string, string> = {
  adzuna:   "Adzuna",
  remotive: "Remotive",
  remoteok: "Remote OK",
  themuse:  "The Muse",
};

const COUNT_OPTIONS = [10, 25, 50, 100, 200];

export default function SettingsPage() {
  const [settings, setSettings] = useState<SourceSetting[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/settings`)
      .then((r) => r.json())
      .then(setSettings)
      .catch(() => setError("Could not load settings. Is the backend running?"));
  }, []);

  const update = (source: string, field: keyof SourceSetting, value: unknown) => {
    setSettings((prev: SourceSetting[]) =>
      prev.map((s) => (s.source === source ? { ...s, [field]: value } : s))
    );
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (!res.ok) throw new Error();
      setSaved(true);
    } catch {
      setError("Failed to save settings.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings-page">
      <div className="settings-page-header">
        <div>
          <Link to="/" className="settings-back">← Dashboard</Link>
          <h1 className="settings-title">Auto-Scan Settings</h1>
          <p className="settings-sub">Configure which sources run during the daily 06:00 scan.</p>
        </div>
        <div className="settings-save-row">
          {saved && <span className="settings-saved-msg">Saved</span>}
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={saving || settings.length === 0}
          >
            {saving ? "Saving…" : "Save Settings"}
          </button>
        </div>
      </div>

      {error && <div className="settings-error">{error}</div>}

      {settings.map((s) => (
        <div
          key={s.source}
          className={`settings-card${s.enabled ? "" : " settings-card--disabled"}`}
        >
          <div className="settings-card-header">
            <label className="settings-enable-label">
              <input
                type="checkbox"
                checked={s.enabled}
                onChange={(e) => update(s.source, "enabled", e.target.checked)}
              />
              <span className="settings-source-name">
                {SOURCE_LABELS[s.source] ?? s.source}
              </span>
            </label>
            {!s.enabled && <span className="settings-disabled-tag">Disabled</span>}
          </div>

          <div className="settings-fields">
            <div className="settings-field">
              <label className="settings-field-label">Keywords</label>
              <input
                type="text"
                className="field-input"
                style={{ width: "200px" }}
                value={s.keywords}
                onChange={(e) => update(s.source, "keywords", e.target.value)}
                placeholder="e.g. software engineer"
              />
            </div>

            {/* Location only applies to Adzuna — other sources don't support it */}
            {s.source === "adzuna" && (
              <div className="settings-field">
                <label className="settings-field-label">Location</label>
                <input
                  type="text"
                  className="field-input"
                  style={{ width: "240px" }}
                  value={s.location}
                  onChange={(e) => update(s.source, "location", e.target.value)}
                  placeholder="e.g. New York (blank = remote)"
                />
              </div>
            )}

            <div className="settings-field">
              <label className="settings-field-label">Results per scan</label>
              <select
                className="field-select"
                value={s.count}
                onChange={(e) => update(s.source, "count", Number(e.target.value))}
              >
                {COUNT_OPTIONS.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
