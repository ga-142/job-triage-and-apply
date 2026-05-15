import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

const API = "/api";

interface Section {
  key: "resume" | "writing-sample" | "instructions";
  title: string;
  description: string;
  placeholder: string;
  rows: number;
}

const SECTIONS: Section[] = [
  {
    key: "resume",
    title: "Resume",
    description:
      "Paste your resume as plain text. The full content is sent to the AI on every scan and document generation — include everything relevant to the roles you're targeting.",
    placeholder: "Paste your resume here…",
    rows: 22,
  },
  {
    key: "writing-sample",
    title: "Writing Sample",
    description:
      "A few paragraphs of your own writing — a past cover letter, a bio, anything that sounds like you. The AI mirrors this tone when generating resumes and cover letters.",
    placeholder: "Paste a writing sample here…",
    rows: 12,
  },
  {
    key: "instructions",
    title: "Document Instructions",
    description:
      "Rules the AI must follow when writing your resume and cover letters. Use this to ban buzzwords, set tone, or enforce style preferences.",
    placeholder: `e.g.\n- Do not use words like "passionate", "ninja", or "synergy"\n- Keep the tone direct and technically grounded\n- Never start a bullet point with "I"`,
    rows: 12,
  },
];

export default function ProfilePage() {
  const [content, setContent] = useState<Record<string, string>>({
    resume: "",
    "writing-sample": "",
    instructions: "",
  });
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const savedTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    Promise.all(
      SECTIONS.map((s) =>
        fetch(`${API}/profile/${s.key}`)
          .then((r) => r.json())
          .then((data) => [s.key, data.content ?? ""] as const)
      )
    )
      .then((pairs) =>
        setContent(Object.fromEntries(pairs))
      )
      .catch(() => setError("Could not load profile. Is the backend running?"));

    return () => {
      if (savedTimer.current) clearTimeout(savedTimer.current);
    };
  }, []);

  const handleSave = async (key: string) => {
    setSaving(key);
    setError(null);
    try {
      const res = await fetch(`${API}/profile/${key}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: content[key] }),
      });
      if (!res.ok) throw new Error();
      setSaved(key);
      if (savedTimer.current) clearTimeout(savedTimer.current);
      savedTimer.current = setTimeout(() => setSaved(null), 2500);
    } catch {
      setError(`Failed to save ${key}.`);
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="settings-page">
      <div className="settings-page-header">
        <div>
          <Link to="/" className="settings-back">← Dashboard</Link>
          <h1 className="settings-title">Profile</h1>
          <p className="settings-sub">
            Your resume and writing preferences. Changes take effect immediately — no restart needed.
          </p>
        </div>
      </div>

      {error && <div className="settings-error">{error}</div>}

      {SECTIONS.map((s) => (
        <div key={s.key} className="settings-card profile-section">
          <div className="settings-card-header">
            <span className="settings-source-name">{s.title}</span>
          </div>

          <p className="profile-section-desc">{s.description}</p>

          <textarea
            className="field-textarea"
            rows={s.rows}
            placeholder={s.placeholder}
            value={content[s.key]}
            onChange={(e) =>
              setContent((prev) => ({ ...prev, [s.key]: e.target.value }))
            }
            spellCheck={false}
          />

          <div className="profile-section-footer">
            {saved === s.key && (
              <span className="settings-saved-msg">Saved</span>
            )}
            <button
              className="btn-primary"
              onClick={() => handleSave(s.key)}
              disabled={saving === s.key}
            >
              {saving === s.key ? "Saving…" : `Save ${s.title}`}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
