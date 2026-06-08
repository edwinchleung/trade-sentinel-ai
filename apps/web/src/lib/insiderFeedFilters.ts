import type { SmartMoneyFeedItem } from "@/lib/api";

export type SideFilter = "all" | "buy" | "sell" | "notable" | "cluster";

const NOTABLE_NOTIONAL = 1_000_000;
const OPEN_MARKET_CODES = new Set(["P", "S"]);
const EXCLUDED_CODES = new Set(["A", "M", "G", "F"]);

function normalizeCode(code: string | null | undefined): string {
  return (code ?? "").trim().toUpperCase().slice(0, 1);
}

function isOpenMarketCode(code: string | null | undefined): boolean {
  return OPEN_MARKET_CODES.has(normalizeCode(code));
}

function classifySide(
  code: string | null | undefined,
  acquiredDisposed: string | null | undefined,
  isOpenMarket: boolean
): SmartMoneyFeedItem["side"] {
  const normalized = normalizeCode(code);
  if (isOpenMarket) {
    if (normalized === "S") return "sell";
    if (normalized === "P") return "buy";
    const ad = (acquiredDisposed ?? "").trim().toUpperCase().slice(0, 1);
    if (ad === "D") return "sell";
    if (ad === "A") return "buy";
  }
  if (EXCLUDED_CODES.has(normalized)) return "other";
  if (normalized === "P") return "buy";
  if (normalized === "S") return "sell";
  return "other";
}

export function normalizeFeedItem(item: SmartMoneyFeedItem): SmartMoneyFeedItem {
  const code = item.transaction_code;
  const isOpenMarket = code
    ? isOpenMarketCode(code)
    : Boolean(item.is_open_market);

  const side = code
    ? classifySide(code, null, isOpenMarket)
    : item.side === "buy" || item.side === "sell" || item.side === "other"
      ? item.side
      : "other";

  const notional =
    item.notional ??
    (item.shares != null && item.price != null
      ? Math.round(item.shares * item.price * 100) / 100
      : null);

  const isNotable = notional != null && notional >= NOTABLE_NOTIONAL;

  return {
    ...item,
    is_open_market: isOpenMarket,
    side,
    notional,
    is_notable: isNotable,
  };
}

export function detectClusterBuying(
  items: SmartMoneyFeedItem[],
  windowDays = 7
): SmartMoneyFeedItem[] {
  const cutoff = Date.now() - windowDays * 86400000;
  const byTicker: Record<string, Set<string>> = {};
  for (const item of items) {
    if (!item.is_open_market || item.side !== "buy" || !item.ticker) continue;
    const ts = Date.parse(item.filing_date);
    if (Number.isNaN(ts) || ts < cutoff) continue;
    const key = item.ticker;
    if (!byTicker[key]) byTicker[key] = new Set();
    if (item.insider_name) byTicker[key].add(item.insider_name);
  }
  const clusterTickers = new Set(
    Object.entries(byTicker)
      .filter(([, insiders]) => insiders.size >= 2)
      .map(([ticker]) => ticker)
  );
  return items.map((item) => ({
    ...item,
    cluster_buying: item.ticker ? clusterTickers.has(item.ticker) : item.cluster_buying,
  }));
}

export function applyClientFilters(
  items: SmartMoneyFeedItem[],
  sideFilter: SideFilter,
  openMarketOnly: boolean
): SmartMoneyFeedItem[] {
  let normalized = items.map(normalizeFeedItem);
  if (openMarketOnly) {
    normalized = normalized.filter((item) => item.is_open_market);
  }
  normalized = detectClusterBuying(normalized);
  return normalized.filter((item) => {
    if (sideFilter === "buy" && item.side !== "buy") return false;
    if (sideFilter === "sell" && item.side !== "sell") return false;
    if (sideFilter === "notable" && !item.is_notable) return false;
    if (sideFilter === "cluster" && !item.cluster_buying) return false;
    return true;
  });
}
