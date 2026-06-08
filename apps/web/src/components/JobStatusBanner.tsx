"use client";

import { ScanProgressBar } from "@/components/ScanProgressBar";
import type { BackgroundJobsStatusResponse } from "@/lib/api";
import type { ScanProgress } from "@/hooks/useJobUpdates";
import { jobLabel, scanProgressLabel } from "@/lib/jobLabels";

function formatJobTime(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function resolveActiveJob(
  status: BackgroundJobsStatusResponse,
  jobName?: string
) {
  if (jobName) {
    return status.jobs.find((j) => j.name === jobName) ?? null;
  }
  if (status.active_job) {
    return status.jobs.find((j) => j.name === status.active_job) ?? null;
  }
  return status.jobs.find((j) => j.status === "running") ?? null;
}

function progressFromJob(
  job: NonNullable<ReturnType<typeof resolveActiveJob>>
): { completed: number; total: number; label: string } | null {
  if (job.progress_total && job.progress_total > 0 && job.progress_completed != null) {
    return {
      completed: job.progress_completed,
      total: job.progress_total,
      label: job.phase || job.label || jobLabel(job.name, job.label),
    };
  }
  return null;
}

export function JobStatusBanner({
  jobName,
  status,
  scanProgress,
  connected = true,
  scanResource,
}: {
  jobName?: string;
  status: BackgroundJobsStatusResponse | null;
  scanProgress?: ScanProgress | null;
  connected?: boolean;
  scanResource?: string;
}) {
  if (!status) return null;

  const runningJobs = status.jobs.filter((j) => j.status === "running");
  const running = runningJobs.length > 0 || status.warming;
  const activeJob = resolveActiveJob(status, jobName);

  const scanMatchesJob =
    scanProgress &&
    scanProgress.total > 0 &&
    (!jobName ||
      !scanProgress.job_name ||
      scanProgress.job_name === jobName ||
      scanProgress.job_name === status.active_job);

  const scanMatchesResource =
    scanProgress &&
    scanResource &&
    scanProgress.resource === scanResource &&
    scanProgress.total > 0;

  const jobProgress = activeJob ? progressFromJob(activeJob) : null;

  const showScanBar = (scanMatchesJob || scanMatchesResource) && scanProgress;
  const showJobBar = !showScanBar && jobProgress;

  const primaryLabel = activeJob
    ? jobLabel(activeJob.name, activeJob.label)
    : runningJobs[0]
      ? jobLabel(runningJobs[0].name, runningJobs[0].label)
      : "Background jobs";

  const primaryPhase =
    (showScanBar && scanProgress?.phase) ||
    activeJob?.phase ||
    (showJobBar && jobProgress?.label) ||
    null;

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-xs text-zinc-500 space-y-2">
      {running && (
        <div className="space-y-1">
          <p className="text-amber-400/90">
            {primaryLabel}
            {primaryPhase ? ` — ${primaryPhase}` : " — in progress"}
            {!connected && " (reconnecting live updates)"}
          </p>
          {status.batch_position && status.batch_total && status.batch_total > 0 && (
            <p className="text-zinc-500">
              Background refresh {status.batch_position}/{status.batch_total}
            </p>
          )}
        </div>
      )}

      {showScanBar && (
        <ScanProgressBar
          completed={scanProgress.completed}
          total={scanProgress.total}
          label={
            scanProgress.phase ||
            scanProgressLabel(
              scanProgress.resource,
              scanProgress.universe,
              scanProgress.watchlist_name
            )
          }
          running={running}
        />
      )}

      {showJobBar && jobProgress && (
        <ScanProgressBar
          completed={jobProgress.completed}
          total={jobProgress.total}
          label={jobProgress.label}
          running={running}
        />
      )}

      {activeJob && (
        <p>
          {jobLabel(activeJob.name, activeJob.label)}: {activeJob.status}
          {activeJob.last_run_at && ` · last run ${formatJobTime(activeJob.last_run_at)}`}
          {activeJob.last_error &&
            activeJob.status === "error" &&
            !running &&
            !status.warming && (
              <span className="text-red-400/90"> · {activeJob.last_error}</span>
            )}
          {activeJob.status === "error" && (running || status.warming) && (
            <span className="text-zinc-500"> · retry queued in background refresh</span>
          )}
        </p>
      )}

      {!activeJob && runningJobs.length > 1 && (
        <ul className="space-y-0.5">
          {runningJobs.map((j) => (
            <li key={j.name}>
              {jobLabel(j.name, j.label)}
              {j.phase ? ` — ${j.phase}` : ""}
            </li>
          ))}
        </ul>
      )}

      {!activeJob && status.market_screener_scanned_count > 0 && !running && (
        <p>
          Market screener cache: {status.market_screener_scanned_count} tickers
          {status.background_jobs_enabled ? " · auto-refresh enabled" : ""}
        </p>
      )}
    </div>
  );
}
