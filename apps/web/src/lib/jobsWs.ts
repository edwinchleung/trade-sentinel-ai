import type { BackgroundJobsStatusResponse, DigestTickerRow } from "@/lib/api";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

function wsBaseUrl(): string {
  if (API_BASE.startsWith("https://")) return API_BASE.replace(/^https/, "wss");
  return API_BASE.replace(/^http/, "ws");
}

export type JobsSnapshotEvent = BackgroundJobsStatusResponse & {
  type: "jobs_snapshot";
  warming?: boolean;
};

export type JobStartedEvent = { type: "job_started"; name: string };
export type JobFinishedEvent = {
  type: "job_finished";
  name: string;
  status: string;
  last_error?: string | null;
};

export type ScanProgressEvent = {
  type: "scan_progress";
  resource: string;
  cache_key: string;
  completed: number;
  total: number;
  percent: number;
  phase?: string;
  job_name?: string;
  universe?: string;
  watchlist_name?: string;
};

export type ScreenerRowsEvent = {
  type: "screener_rows";
  universe: string;
  rows: DigestTickerRow[];
  completed: number;
  total: number;
  stale: boolean;
};

export type DigestRowsEvent = {
  type: "digest_rows";
  watchlist_name: string;
  rows: DigestTickerRow[];
  completed: number;
  total: number;
};

export type JobWsEvent =
  | JobsSnapshotEvent
  | JobStartedEvent
  | JobFinishedEvent
  | ScanProgressEvent
  | ScreenerRowsEvent
  | DigestRowsEvent;

export type JobWsHandlers = {
  onEvent?: (event: JobWsEvent) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: () => void;
};

export type JobsWebSocketHandle = {
  disconnect: () => void;
  setChannels: (channels: string[]) => void;
};

export function connectJobsWebSocket(
  channels: string[],
  handlers: JobWsHandlers
): JobsWebSocketHandle {
  let ws: WebSocket | null = null;
  let closed = false;
  let retryMs = 1000;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let currentChannels = channels;

  const subscribe = () => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: "subscribe", channels: currentChannels }));
    }
  };

  const connect = () => {
    if (closed) return;
    ws = new WebSocket(`${wsBaseUrl()}/api/v1/ws`);
    ws.onopen = () => {
      retryMs = 1000;
      handlers.onOpen?.();
      subscribe();
    };
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data as string) as JobWsEvent;
        if (data && typeof data === "object" && "type" in data) {
          handlers.onEvent?.(data);
        }
      } catch {
        /* ignore */
      }
    };
    ws.onerror = () => handlers.onError?.();
    ws.onclose = () => {
      handlers.onClose?.();
      if (!closed) {
        retryTimer = setTimeout(() => {
          retryMs = Math.min(retryMs * 2, 30000);
          connect();
        }, retryMs);
      }
    };
  };

  connect();

  return {
    disconnect: () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      ws?.close();
    },
    setChannels: (next: string[]) => {
      currentChannels = next;
      subscribe();
    },
  };
}
