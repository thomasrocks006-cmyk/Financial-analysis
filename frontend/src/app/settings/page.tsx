"use client";

import { Settings as SettingsIcon, Key, Server } from "lucide-react";

export default function SettingsPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-xl font-bold text-[var(--text-primary)]">
        Settings
      </h1>

      {/* API Connection */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="flex items-center gap-2 mb-3">
          <Server className="h-4 w-4 text-[var(--accent)]" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            API Connection
          </h2>
        </div>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs text-[var(--text-muted)]">
              Backend URL
            </label>
            <input
              type="text"
              defaultValue={apiUrl}
              readOnly
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text-secondary)] font-mono"
            />
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Set via NEXT_PUBLIC_API_URL environment variable
            </p>
          </div>
        </div>
      </div>

      {/* About */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="flex items-center gap-2 mb-3">
          <SettingsIcon className="h-4 w-4 text-[var(--accent)]" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            About
          </h2>
        </div>
        <div className="space-y-2 text-sm text-[var(--text-secondary)]">
          <p>AI Infrastructure Research Platform — Premium Frontend</p>
          <p className="text-xs text-[var(--text-muted)]">
            Session 16: Next.js + React + TailwindCSS
          </p>
          <p className="text-xs text-[var(--text-muted)]">
            15-stage pipeline with live SSE tracking, report generation,
            audit quality scoring, and full backend integration.
          </p>
        </div>
      </div>
    </div>
  );
}
