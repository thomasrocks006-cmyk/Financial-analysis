import { STAGE_LABELS, type RunSummary } from "@/lib/types";

export type RunFilter = "all" | "running" | "failed" | "completed" | "queued";
export type SortMode = "recent" | "progress" | "updated" | "status";

type RunAction = {
	href: string;
	label: string;
};

export function statusColor(status: string) {
	if (status === "running") return "text-[var(--accent)]";
	if (status === "completed") return "text-[var(--success)]";
	if (status === "failed") return "text-[var(--error)]";
	return "text-[var(--text-muted)]";
}

export function formatRunProgress(run: {
	completed_stage_count?: number;
	current_stage?: number | null;
	status: string;
}) {
	const completed = run.completed_stage_count ?? 0;
	if (run.status === "completed") return "15 / 15";
	if (run.status === "failed") return `${completed} / 15 · BLOCKED`;
	if (run.status === "running" && run.current_stage != null) {
		return `${completed} / 15 · S${String(run.current_stage).padStart(2, "0")}`;
	}
	if (run.status === "queued") return "0 / 15 · QUEUED";
	return `${completed} / 15`;
}

export function getRunProgressPercent(run: {
	progress_pct?: number;
	completed_stage_count?: number;
	status: string;
}) {
	if (run.status === "completed") return 100;
	return Math.max(
		0,
		Math.min(100, run.progress_pct ?? ((run.completed_stage_count ?? 0) / 15) * 100)
	);
}

export function getRunStageLabel(run: Pick<RunSummary, "status" | "current_stage">) {
	if (run.status === "queued") return "Awaiting bootstrap";
	if (run.status === "completed") return STAGE_LABELS[14];
	if (run.current_stage != null) {
		return STAGE_LABELS[run.current_stage] ?? `Stage ${run.current_stage}`;
	}
	if (run.status === "failed") return "Pipeline blocked";
	return "No stage signal";
}

export function getProgressBarTone(status: string) {
	if (status === "completed") return "bg-[var(--success)]";
	if (status === "failed") return "bg-[var(--error)]";
	if (status === "running") return "bg-[var(--accent)]";
	return "bg-[var(--text-muted)]";
}

export function formatEventLabel(
	run: Pick<RunSummary, "last_event_type" | "last_event_label" | "last_event_stage">
) {
	if (run.last_event_label) return run.last_event_label;
	if (run.last_event_stage != null) {
		return STAGE_LABELS[run.last_event_stage] ?? `Stage ${run.last_event_stage}`;
	}
	return run.last_event_type ? run.last_event_type.replace(/_/g, " ") : "Awaiting events";
}

export function getBlockedStageLabel(run: Pick<RunSummary, "status" | "current_stage">) {
	if (run.status !== "failed" || run.current_stage == null) return null;
	const label = STAGE_LABELS[run.current_stage] ?? `Stage ${run.current_stage}`;
	return `Blocked at S${String(run.current_stage).padStart(2, "0")} · ${label}`;
}

export function getRowActions(
	run: Pick<RunSummary, "run_id" | "status" | "current_stage">
): RunAction[] {
	if (run.status === "failed") {
		return [
			{ href: `/audit?run_id=${run.run_id}#gate-console`, label: "Audit" },
			{ href: `/quant?run_id=${run.run_id}#run-selector`, label: "Quant" },
		];
	}
	if (run.current_stage === 12) {
		return [{ href: `/portfolio?run_id=${run.run_id}#construction-overlay`, label: "Portfolio" }];
	}
	if (run.current_stage === 9 || run.current_stage === 10) {
		return [{ href: `/quant?run_id=${run.run_id}#run-selector`, label: "Quant" }];
	}
	if (run.current_stage === 5 || run.current_stage === 11) {
		return [{ href: `/audit?run_id=${run.run_id}#gate-console`, label: "Audit" }];
	}
	if (run.status === "completed") {
		return [{ href: `/runs/${run.run_id}`, label: "Open" }];
	}
	return [];
}

export function formatRelativeTimestamp(timestamp: string | null | undefined) {
	if (!timestamp) return "no updates yet";
	const then = new Date(timestamp).getTime();
	if (Number.isNaN(then)) return "time unavailable";
	const diffMs = then - Date.now();
	const absSeconds = Math.round(Math.abs(diffMs) / 1000);
	const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

	if (absSeconds < 60) return rtf.format(Math.round(diffMs / 1000), "second");
	if (absSeconds < 3600) return rtf.format(Math.round(diffMs / 60000), "minute");
	if (absSeconds < 86400) return rtf.format(Math.round(diffMs / 3600000), "hour");
	return rtf.format(Math.round(diffMs / 86400000), "day");
}

export function getStatusRank(status: string) {
	if (status === "failed") return 0;
	if (status === "running") return 1;
	if (status === "queued") return 2;
	if (status === "completed") return 3;
	return 4;
}

export function getEventFreshnessMeta(
	run: Pick<RunSummary, "status" | "last_event_at">,
	now = Date.now()
) {
	if (!run.last_event_at) {
		if (run.status === "queued") {
			return {
				label: "QUEUED",
				detail: "awaiting first event",
				tone: "border-[var(--border)] text-[var(--text-muted)]",
				stale: false,
			};
		}
		return {
			label: "NO FEED",
			detail: "no event timestamp",
			tone: "border-[var(--border)] text-[var(--text-muted)]",
			stale: false,
		};
	}

	const ageMs = Math.max(0, now - new Date(run.last_event_at).getTime());
	if (ageMs <= 60_000) {
		return {
			label: "ACTIVE",
			detail: formatRelativeTimestamp(run.last_event_at),
			tone: "border-[var(--accent)] text-[var(--accent)]",
			stale: false,
		};
	}
	if (ageMs <= 5 * 60_000) {
		return {
			label: "RECENT",
			detail: formatRelativeTimestamp(run.last_event_at),
			tone: "border-[var(--info)] text-[var(--info)]",
			stale: false,
		};
	}
	if (ageMs <= 15 * 60_000) {
		return {
			label: "QUIET",
			detail: formatRelativeTimestamp(run.last_event_at),
			tone: "border-[var(--warning)] text-[var(--warning)]",
			stale: false,
		};
	}
	return {
		label: "STALE",
		detail: formatRelativeTimestamp(run.last_event_at),
		tone: "border-[var(--error)] text-[var(--error)]",
		stale: true,
	};
}
