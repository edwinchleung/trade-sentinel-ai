"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import {
  connectJobsWebSocket,
  type DigestRowsEvent,
  type JobWsEvent,
  type ScanProgressEvent,
  type ScreenerRowsEvent,
} from "@/lib/jobsWs";
import type { BackgroundJobsStatusResponse } from "@/lib/api";
import { fetchJobStatus } from "@/lib/api";
import { useJobUpdatesContext } from "@/components/JobUpdatesProvider";

export type ScanProgress = {
  resource: string;
  completed: number;
  total: number;
  percent: number;
  phase?: string;
  job_name?: string;
  universe?: string;
  watchlist_name?: string;
};

export function useJobUpdates(
  channels: string[],
  options?: {
    onScreenerRows?: (ev: ScreenerRowsEvent) => void;
    onDigestRows?: (ev: DigestRowsEvent) => void;
    onJobFinished?: (name: string, status: string) => void;
  }
) {
  const ctx = useJobUpdatesContext();
  const fallbackId = useId();
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const channelsKey = useMemo(
    () => channels.slice().sort().join(","),
    [channels]
  );

  useEffect(() => {
    if (!ctx) return;
    return ctx.register(fallbackId, channels, {
      onScreenerRows: (ev) => optionsRef.current?.onScreenerRows?.(ev),
      onDigestRows: (ev) => optionsRef.current?.onDigestRows?.(ev),
      onJobFinished: (name, status) =>
        optionsRef.current?.onJobFinished?.(name, status),
    });
  }, [ctx, fallbackId, channelsKey, channels]);

  const [fallbackStatus, setFallbackStatus] = useState<BackgroundJobsStatusResponse | null>(null);
  const [fallbackScanProgress, setFallbackScanProgress] = useState<ScanProgress | null>(null);
  const [fallbackConnected, setFallbackConnected] = useState(false);

  const handleEvent = useCallback((event: JobWsEvent) => {
    if (event.type === "jobs_snapshot") {
      setFallbackStatus({
        as_of: event.as_of,
        jobs: event.jobs,
        market_screener_scanned_count: event.market_screener_scanned_count,
        background_jobs_enabled: event.background_jobs_enabled,
        warming: event.warming,
        active_job: event.active_job,
        batch_position: event.batch_position,
        batch_total: event.batch_total,
      });
      return;
    }
    if (event.type === "scan_progress") {
      const e = event as ScanProgressEvent;
      setFallbackScanProgress({
        resource: e.resource,
        completed: e.completed,
        total: e.total,
        percent: e.percent,
        phase: e.phase,
        job_name: e.job_name,
        universe: e.universe,
        watchlist_name: e.watchlist_name,
      });
      return;
    }
    if (event.type === "screener_rows") {
      optionsRef.current?.onScreenerRows?.(event);
      return;
    }
    if (event.type === "digest_rows") {
      optionsRef.current?.onDigestRows?.(event);
      return;
    }
    if (event.type === "job_finished") {
      optionsRef.current?.onJobFinished?.(event.name, event.status);
      return;
    }
    if (event.type === "job_started") {
      setFallbackScanProgress(null);
    }
  }, []);

  useEffect(() => {
    if (ctx) return;
    const ch = channels;
    fetchJobStatus()
      .then(setFallbackStatus)
      .catch(() => setFallbackStatus(null));

    const handle = connectJobsWebSocket(ch, {
      onOpen: () => setFallbackConnected(true),
      onClose: () => setFallbackConnected(false),
      onEvent: handleEvent,
    });

    return () => {
      handle.disconnect();
      setFallbackConnected(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- channelsKey replaces channels
  }, [ctx, channelsKey, handleEvent]);

  if (ctx) {
    return {
      status: ctx.status,
      scanProgress: ctx.scanProgress,
      connected: ctx.connected,
      setScanProgress: ctx.setScanProgress,
    };
  }

  return {
    status: fallbackStatus,
    scanProgress: fallbackScanProgress,
    connected: fallbackConnected,
    setScanProgress: setFallbackScanProgress,
  };
}
