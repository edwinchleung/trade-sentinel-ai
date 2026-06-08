import type { SmartMoneyFeedItem } from "@/lib/api";
import { normalizeFeedItem } from "@/lib/insiderFeedFilters";

export { detectClusterBuying } from "@/lib/insiderFeedFilters";

const STORAGE_KEY = "tradesentinel:insider_feed_archive:v1";
const RETENTION_DAYS = 90;

type ArchivedItem = SmartMoneyFeedItem & {
  id: string;
  fetched_at: string;
};

type ArchivePayload = {
  items: ArchivedItem[];
  updated_at: string;
};

function accessionFromUrl(url: string | null | undefined): string {
  if (!url) return "";
  const match = url.match(/(\d{10}-\d{2}-\d{6})/);
  return match?.[1] ?? "";
}

export function itemStableId(item: SmartMoneyFeedItem): string {
  const acc = accessionFromUrl(item.filing_url);
  const parts = [
    acc,
    item.filing_date,
    item.insider_name ?? "",
    item.transaction_code ?? "",
    item.shares ?? "",
    item.side,
  ];
  const key = parts.join("|");
  if (key.replace(/\|/g, "").length > 0) return key;
  return `hash:${hashString(JSON.stringify(item))}`;
}

function hashString(input: string): string {
  let h = 0;
  for (let i = 0; i < input.length; i += 1) {
    h = (Math.imul(31, h) + input.charCodeAt(i)) | 0;
  }
  return String(h);
}

function readArchive(): ArchivePayload {
  if (typeof window === "undefined") return { items: [], updated_at: "" };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { items: [], updated_at: "" };
    const parsed = JSON.parse(raw) as ArchivePayload;
    if (!Array.isArray(parsed.items)) return { items: [], updated_at: "" };
    return parsed;
  } catch {
    return { items: [], updated_at: "" };
  }
}

function writeArchive(payload: ArchivePayload): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    const trimmed = payload.items.slice(Math.floor(payload.items.length * 0.1));
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...payload, items: trimmed }));
    } catch {
      /* quota still exceeded */
    }
  }
}

export function pruneArchive(retentionDays = RETENTION_DAYS): void {
  const cutoff = Date.now() - retentionDays * 86400000;
  const archive = readArchive();
  archive.items = archive.items.filter((item) => {
    const ts = Date.parse(item.fetched_at);
    if (Number.isNaN(ts)) return true;
    return ts >= cutoff;
  });
  writeArchive(archive);
}

export function mergeItems(incoming: SmartMoneyFeedItem[]): { total: number; added: number } {
  pruneArchive();
  const archive = readArchive();
  const byId = new Map(archive.items.map((i) => [i.id, i]));
  const now = new Date().toISOString();
  let added = 0;
  for (const item of incoming) {
    const normalized = normalizeFeedItem(item);
    const id = itemStableId(normalized);
    if (!byId.has(id)) added += 1;
    byId.set(id, { ...normalized, id, fetched_at: now });
  }
  const items = Array.from(byId.values()).sort((a, b) =>
    b.filing_date.localeCompare(a.filing_date)
  );
  writeArchive({ items, updated_at: now });
  return { total: items.length, added };
}

export function itemsInRange(start: string, end: string): SmartMoneyFeedItem[] {
  pruneArchive();
  const archive = readArchive();
  return archive.items
    .filter((item) => {
      const d = item.filing_date.slice(0, 10);
      return d >= start && d <= end;
    })
    .map((item) => normalizeFeedItem(item));
}

export function archiveStats(): { count: number; updated_at: string | null } {
  const archive = readArchive();
  return { count: archive.items.length, updated_at: archive.updated_at || null };
}

export function clearArchive(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
}
