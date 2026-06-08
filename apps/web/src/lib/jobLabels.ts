/** Human-readable labels for background job names (mirrors API JOB_META). */
export const JOB_LABELS: Record<string, string> = {
  digest: "Daily digest",
  market_screener: "Market screener",
  smart_money_feed: "Insider feed",
  watchlist_pulse: "Watchlist insider pulse",
  options_watchlist: "Options scan (watchlist)",
  options_sp100: "Options scan (S&P 100)",
  options_sp500: "Options scan (S&P 500)",
  volume_watchlist: "Volume scan (watchlist)",
  volume_sp500: "Volume scan (S&P 500)",
  insider_sp500: "Insider scan (S&P 500)",
  institutional_conviction: "13F institutional conviction",
  activist_feed: "Activist feed",
  cot_macro: "COT macro report",
};

export function jobLabel(name: string, fallbackLabel?: string | null): string {
  return fallbackLabel || JOB_LABELS[name] || name.replace(/_/g, " ");
}

export function scanProgressLabel(resource: string, universe?: string, watchlistName?: string): string {
  if (resource === "market_screener") {
    return `Market screener (${universe ?? "universe"})`;
  }
  if (resource === "digest") {
    return `Digest (${watchlistName ?? "default"})`;
  }
  if (resource === "smart_money_feed") {
    return "Insider feed (Form 4)";
  }
  if (resource === "options_scan") {
    return `Options scan (${universe ?? "universe"})`;
  }
  if (resource === "volume_scan") {
    return `Volume scan (${universe ?? "universe"})`;
  }
  return resource.replace(/_/g, " ");
}
