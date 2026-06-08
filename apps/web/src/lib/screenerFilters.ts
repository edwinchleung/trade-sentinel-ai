import type { DigestTickerRow, ScreenerRow } from "@/lib/api";

export type ScreenerFilterInput = {
  preset?: string;
  mos_min?: number;
  mos_max?: number;
  pe_max?: number;
  valuation_label?: string;
  has_earnings_within_days?: number;
  insider_sentiment?: string;
  warning_any?: string;
};

function rankScore(row: DigestTickerRow, preset?: string): number {
  if (row.mos_pct == null) return preset === "undervalued" ? 999 : -999;
  return row.mos_pct;
}

export function applyScreenerFiltersClient(
  rows: DigestTickerRow[],
  filters: ScreenerFilterInput
): ScreenerRow[] {
  let mos_label: string | undefined;
  let has_earnings_within_days = filters.has_earnings_within_days;
  let insider_sentiment = filters.insider_sentiment;
  let warning_any = filters.warning_any;

  if (filters.preset === "undervalued") mos_label = "undervalued";
  else if (filters.preset === "earnings_week") has_earnings_within_days = has_earnings_within_days ?? 7;
  else if (filters.preset === "insider_accumulation") insider_sentiment = insider_sentiment ?? "accumulation";
  else if (filters.preset === "insider_cluster_buy") insider_sentiment = insider_sentiment ?? "accumulation";
  else if (filters.preset === "options_unusual") warning_any = warning_any ?? "OPTIONS_UNUSUAL";
  else if (filters.preset === "high_risk") warning_any = warning_any ?? "PRICE_ABOVE_FAIR_VALUE";

  const matched: ScreenerRow[] = [];
  for (const row of rows) {
    if (mos_label && row.mos_label !== mos_label) continue;
    if (filters.mos_min != null && (row.mos_pct == null || row.mos_pct < filters.mos_min)) continue;
    if (filters.mos_max != null && (row.mos_pct == null || row.mos_pct > filters.mos_max)) continue;
    if (filters.pe_max != null && (row.pe_forward == null || row.pe_forward > filters.pe_max)) continue;
    if (filters.valuation_label && row.valuation_label !== filters.valuation_label) continue;
    if (has_earnings_within_days != null) {
      if (row.earnings_days == null || row.earnings_days > has_earnings_within_days) continue;
    }
    if (warning_any && row.top_warning !== warning_any) continue;
    if (insider_sentiment && row.insider_sentiment !== insider_sentiment) continue;
    matched.push({ ...row, rank_score: rankScore(row, filters.preset) });
  }

  if (filters.preset === "undervalued") {
    matched.sort((a, b) => (a.rank_score ?? 999) - (b.rank_score ?? 999));
  } else {
    matched.sort((a, b) => (b.rank_score ?? -999) - (a.rank_score ?? -999));
  }
  return matched;
}

export function mergeRowsByTicker<T extends { ticker: string }>(
  existing: T[],
  incoming: T[]
): T[] {
  const map = new Map<string, T>();
  for (const r of existing) map.set(r.ticker.toUpperCase(), r);
  for (const r of incoming) map.set(r.ticker.toUpperCase(), r);
  return Array.from(map.values());
}
