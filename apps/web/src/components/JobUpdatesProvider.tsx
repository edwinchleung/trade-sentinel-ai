"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { JobStatusBanner } from "@/components/JobStatusBanner";
import {
  connectJobsWebSocket,
  type DigestRowsEvent,
  type JobWsEvent,
  type ScreenerRowsEvent,
} from "@/lib/jobsWs";
import type { BackgroundJobsStatusResponse } from "@/lib/api";
import { fetchJobStatus } from "@/lib/api";
import type { ScanProgress } from "@/hooks/useJobUpdates";

type PageHandlers = {
  onScreenerRows?: (ev: ScreenerRowsEvent) => void;
  onDigestRows?: (ev: DigestRowsEvent) => void;
  onJobFinished?: (name: string, status: string) => void;
};

type Registration = {
  channels: string[];
  handlers: PageHandlers;
};

type JobUpdatesContextValue = {
  status: BackgroundJobsStatusResponse | null;
  connected: boolean;
  scanProgress: ScanProgress | null;
  setScanProgress: (p: ScanProgress | null) => void;
  register: (id: string, channels: string[], handlers: PageHandlers) => () => void;
};

const JobUpdatesContext = createContext<JobUpdatesContextValue | null>(null);

function mergeChannels(registrations: Map<string, Registration>): string[] {
  const all = new Set<string>(["jobs"]);
  for (const reg of registrations.values()) {
    for (const ch of reg.channels) all.add(ch);
  }
  return [...all].sort();
}

export function JobUpdatesProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<BackgroundJobsStatusResponse | null>(null);
  const [scanProgress, setScanProgress] = useState<ScanProgress | null>(null);
  const [connected, setConnected] = useState(false);
  const registrationsRef = useRef<Map<string, Registration>>(new Map());
  const wsRef = useRef<ReturnType<typeof connectJobsWebSocket> | null>(null);

  const syncChannels = useCallback(() => {
    wsRef.current?.setChannels(mergeChannels(registrationsRef.current));
  }, []);

  const dispatchEvent = useCallback((event: JobWsEvent) => {
    for (const reg of registrationsRef.current.values()) {
      if (event.type === "screener_rows") {
        reg.handlers.onScreenerRows?.(event);
      }
      if (event.type === "digest_rows") {
        reg.handlers.onDigestRows?.(event);
      }
      if (event.type === "job_finished") {
        reg.handlers.onJobFinished?.(event.name, event.status);
      }
    }
  }, []);

  const handleEvent = useCallback(
    (event: JobWsEvent) => {
      if (event.type === "jobs_snapshot") {
        setStatus({
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
        setScanProgress({
          resource: event.resource,
          completed: event.completed,
          total: event.total,
          percent: event.percent,
          phase: event.phase,
          job_name: event.job_name,
          universe: event.universe,
          watchlist_name: event.watchlist_name,
        });
        dispatchEvent(event);
        return;
      }
      if (event.type === "job_started") {
        setScanProgress(null);
      }
      dispatchEvent(event);
    },
    [dispatchEvent]
  );

  useEffect(() => {
    fetchJobStatus()
      .then(setStatus)
      .catch(() => setStatus(null));

    wsRef.current = connectJobsWebSocket(["jobs"], {
      onOpen: () => setConnected(true),
      onClose: () => setConnected(false),
      onEvent: handleEvent,
    });

    return () => {
      wsRef.current?.disconnect();
      wsRef.current = null;
      setConnected(false);
    };
  }, [handleEvent]);

  const register = useCallback(
    (id: string, channels: string[], handlers: PageHandlers) => {
      registrationsRef.current.set(id, { channels, handlers });
      syncChannels();
      return () => {
        registrationsRef.current.delete(id);
        syncChannels();
      };
    },
    [syncChannels]
  );

  const value = useMemo(
    () => ({
      status,
      connected,
      scanProgress,
      setScanProgress,
      register,
    }),
    [status, connected, scanProgress, register]
  );

  const showBanner = status?.jobs.some((j) => j.status === "running") ?? false;

  return (
    <JobUpdatesContext.Provider value={value}>
      {showBanner && (
        <div className="mx-auto max-w-6xl px-4 pt-2">
          <JobStatusBanner status={status} connected={connected} />
        </div>
      )}
      {children}
    </JobUpdatesContext.Provider>
  );
}

export function useJobUpdatesContext() {
  return useContext(JobUpdatesContext);
}
