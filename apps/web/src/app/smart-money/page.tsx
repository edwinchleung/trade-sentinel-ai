"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchActivistFeed,
  fetchCongressionalFeed,
  fetchCotReport,
  fetchInsiderScan,
  fetchInstitutionalConviction,
  fetchMicrostructure,
  fetchOptionsActivityScan,
  fetchSmartMoneyFeed,
  fetchVolumeScan,
  fetchWatchlistInsiderPulse,
  type ActivistFeed,
  type CongressionalFeed,
  type CotReport,
  type InsiderScanResult,
  type InstitutionalConvictionScan,
  type MicrostructureSnapshot,
  type OptionsScanResult,
  type ScanUniverse,
  type SmartMoneyFeed,
  type SmartMoneyFeedItem,
  type VolumeScanResult,
  type WatchlistInsiderPulse,
} from "@/lib/api";
import {
  archiveStats,
  clearArchive,
  detectClusterBuying,
  itemsInRange,
  mergeItems,
} from "@/lib/insiderFeedArchive";
import { SmartMoneyFeedTable } from "@/components/SmartMoneyFeedTable";
import { WatchlistInsiderPulsePanel } from "@/components/WatchlistInsiderPulsePanel";
import { InsiderScanPanel } from "@/components/InsiderScanPanel";
import { OptionsActivityScanPanel } from "@/components/OptionsActivityScanPanel";
import { VolumeScanPanel } from "@/components/VolumeScanPanel";
import { InstitutionalConvictionPanel } from "@/components/InstitutionalConvictionPanel";
import { ActivistFeedPanel } from "@/components/ActivistFeedPanel";
import { CongressionalPanel, MicrostructurePanel } from "@/components/smart-money/MicrostructurePanels";
import { FundHoldingsPanel } from "@/components/smart-money/FundHoldingsPanel";
import { JobStatusBanner } from "@/components/JobStatusBanner";
import { useJobUpdates } from "@/hooks/useJobUpdates";
import {
  rangeFromPreset,
  type FeedDateRange,
} from "@/components/InsiderFeedDateRange";

type ActivistFormFilter = "all" | "13d" | "13g";

function isEmptySignalsMessage(message: string | null | undefined): boolean {
  if (!message) return false;
  return /no unusual|no accumulation/i.test(message);
}

type Tab =
  | "feed"
  | "pulse"
  | "institutional"
  | "fund"
  | "activist"
  | "options"
  | "volume"
  | "cot"
  | "microstructure"
  | "congressional";

type FormTypeFilter = "4" | "3" | "5" | "all";

const emptyFeed: SmartMoneyFeed = {
  as_of: new Date().toISOString(),
  items: [],
  stats: { buy_count: 0, sell_count: 0, other_count: 0, top_tickers: [] },
  data_available: false,
  days_window: 1,
};

const defaultFeedRange = (): FeedDateRange => {
  const { start, end } = rangeFromPreset("today");
  return { preset: "today", start, end };
};

const emptyPulse: WatchlistInsiderPulse = {
  as_of: new Date().toISOString(),
  watchlist_name: "default",
  rows: [],
  data_available: false,
};

const emptyScan: OptionsScanResult = {
  as_of: new Date().toISOString(),
  universe: "sp500",
  rows: [],
  scanned_count: 0,
  data_available: false,
  disclaimer:
    "Heuristic put/call scan via yfinance — not exchange block-flow or paid unusual-activity data.",
};

const emptyVolumeScan: VolumeScanResult = {
  as_of: new Date().toISOString(),
  universe: "sp500",
  rows: [],
  scanned_count: 0,
  data_available: false,
};

export default function SmartMoneyPage() {
  const [tab, setTab] = useState<Tab>("feed");
  const [feed, setFeed] = useState<SmartMoneyFeed>(emptyFeed);
  const [pulse, setPulse] = useState<WatchlistInsiderPulse>(emptyPulse);
  const [insiderScan, setInsiderScan] = useState<InsiderScanResult | null>(null);
  const [pulseMode, setPulseMode] = useState<"market" | "watchlist">("market");
  const [scan, setScan] = useState<OptionsScanResult>(emptyScan);
  const [volumeScan, setVolumeScan] = useState<VolumeScanResult>(emptyVolumeScan);
  const [activist, setActivist] = useState<ActivistFeed | null>(null);
  const [institutional, setInstitutional] = useState<InstitutionalConvictionScan | null>(null);
  const [cot, setCot] = useState<CotReport | null>(null);
  const [microstructure, setMicrostructure] = useState<MicrostructureSnapshot | null>(null);
  const [congressional, setCongressional] = useState<CongressionalFeed | null>(null);
  const [sideFilter, setSideFilter] = useState<"all" | "buy" | "sell" | "notable" | "cluster">("all");
  const [formTypeFilter, setFormTypeFilter] = useState<FormTypeFilter>("4");
  const [openMarketOnly, setOpenMarketOnly] = useState(true);
  const [feedDateRange, setFeedDateRange] = useState<FeedDateRange>(defaultFeedRange);
  const [feedDisplayItems, setFeedDisplayItems] = useState<SmartMoneyFeedItem[]>([]);
  const [archiveMeta, setArchiveMeta] = useState<{ count: number; updated_at: string | null }>({
    count: 0,
    updated_at: null,
  });
  const [optionsUniverse, setOptionsUniverse] = useState<ScanUniverse>("sp500");
  const [volumeUniverse, setVolumeUniverse] = useState<ScanUniverse>("sp500");
  const [optionsSignalsOnly, setOptionsSignalsOnly] = useState(true);
  const [volumeSignalsOnly, setVolumeSignalsOnly] = useState(true);
  const [activistFormFilter, setActivistFormFilter] = useState<ActivistFormFilter>("all");
  const [optionsBanner, setOptionsBanner] = useState<string | null>(null);
  const [volumeBanner, setVolumeBanner] = useState<string | null>(null);
  const [loadingFeed, setLoadingFeed] = useState(true);
  const [loadingPulse, setLoadingPulse] = useState(false);
  const [loadingScan, setLoadingScan] = useState(false);
  const [loadingOther, setLoadingOther] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const syncFeedFromArchive = useCallback((range: FeedDateRange) => {
    const raw = itemsInRange(range.start, range.end);
    setFeedDisplayItems(detectClusterBuying(raw));
    setArchiveMeta(archiveStats());
  }, []);

  const loadFeed = useCallback(
    async (forceRefresh = false) => {
      setLoadingFeed(true);
      setError(null);
      try {
        const data = await fetchSmartMoneyFeed({
          start_date: feedDateRange.start,
          end_date: feedDateRange.end,
          side: "all",
          open_market_only: false,
          form_type: formTypeFilter,
          refresh: forceRefresh,
        });
        mergeItems(data.items);
        setFeed(data);
        syncFeedFromArchive(feedDateRange);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load market feed");
      } finally {
        setLoadingFeed(false);
      }
    },
    [feedDateRange, formTypeFilter, syncFeedFromArchive]
  );

  const handleFeedDateRangeChange = useCallback(
    (range: FeedDateRange) => {
      setFeedDateRange(range);
      syncFeedFromArchive(range);
    },
    [syncFeedFromArchive]
  );

  const handleClearArchive = useCallback(() => {
    clearArchive();
    syncFeedFromArchive(feedDateRange);
  }, [feedDateRange, syncFeedFromArchive]);

  const loadPulse = useCallback(async () => {
    setLoadingPulse(true);
    setError(null);
    try {
      setPulse(await fetchWatchlistInsiderPulse());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load watchlist pulse");
    } finally {
      setLoadingPulse(false);
    }
  }, []);

  const loadInsiderScan = useCallback(async (universe: ScanUniverse = "sp500") => {
    setLoadingPulse(true);
    setError(null);
    try {
      setInsiderScan(await fetchInsiderScan({ universe }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load insider scan");
    } finally {
      setLoadingPulse(false);
    }
  }, []);

  const loadScan = useCallback(
    async (universe: ScanUniverse, signalsOnly = optionsSignalsOnly) => {
      setLoadingScan(true);
      setError(null);
      try {
        const data = await fetchOptionsActivityScan({ universe, signalsOnly });
        let keptPrior = false;
        setScan((prev) => {
          if (
            signalsOnly &&
            data.rows.length === 0 &&
            prev.rows.length > 0 &&
            isEmptySignalsMessage(data.message)
          ) {
            keptPrior = true;
            return prev;
          }
          return data;
        });
        setOptionsBanner(keptPrior ? data.message ?? null : null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to scan options");
      } finally {
        setLoadingScan(false);
      }
    },
    [optionsSignalsOnly]
  );

  const loadVolumeScan = useCallback(
    async (universe: ScanUniverse, signalsOnly = volumeSignalsOnly) => {
      setLoadingOther(true);
      setError(null);
      try {
        const data = await fetchVolumeScan({ universe, signalsOnly });
        let keptPrior = false;
        setVolumeScan((prev) => {
          if (
            signalsOnly &&
            data.rows.length === 0 &&
            prev.rows.length > 0 &&
            isEmptySignalsMessage(data.message)
          ) {
            keptPrior = true;
            return prev;
          }
          return data;
        });
        setVolumeBanner(keptPrior ? data.message ?? null : null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed volume scan");
      } finally {
        setLoadingOther(false);
      }
    },
    [volumeSignalsOnly]
  );

  const loadActivist = useCallback(
    async (formFilter: ActivistFormFilter = activistFormFilter, refresh = false) => {
      setLoadingOther(true);
      setError(null);
      try {
        setActivist(await fetchActivistFeed({ days: 30, type: formFilter, refresh }));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed activist feed");
      } finally {
        setLoadingOther(false);
      }
    },
    [activistFormFilter]
  );

  const loadTabData = useCallback(async (active: Tab) => {
    if (active === "activist") {
      await loadActivist(activistFormFilter);
    } else if (active === "institutional") {
      setLoadingOther(true);
      try {
        setInstitutional(await fetchInstitutionalConviction({ universe: "sp500" }));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed 13F scan");
      } finally {
        setLoadingOther(false);
      }
    } else if (active === "cot") {
      setLoadingOther(true);
      try {
        setCot(await fetchCotReport());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed COT report");
      } finally {
        setLoadingOther(false);
      }
    } else if (active === "microstructure") {
      setLoadingOther(true);
      try {
        setMicrostructure(await fetchMicrostructure("SPY"));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed microstructure");
      } finally {
        setLoadingOther(false);
      }
    } else if (active === "congressional") {
      setLoadingOther(true);
      try {
        setCongressional(await fetchCongressionalFeed({ days: 30 }));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed congressional feed");
      } finally {
        setLoadingOther(false);
      }
    }
  }, [activistFormFilter, loadActivist]);

  const tabJobName = (() => {
    if (tab === "feed") return "smart_money_feed";
    if (tab === "pulse") return pulseMode === "watchlist" ? "watchlist_pulse" : "insider_sp500";
    if (tab === "options") {
      if (optionsUniverse === "watchlist") return "options_watchlist";
      if (optionsUniverse === "sp100") return "options_sp100";
      return "options_sp500";
    }
    if (tab === "volume") {
      if (volumeUniverse === "watchlist") return "volume_watchlist";
      if (volumeUniverse === "sp100") return "volume_sp100";
      return "volume_sp500";
    }
    if (tab === "institutional") return "institutional_conviction";
    if (tab === "activist") return "activist_feed";
    if (tab === "cot") return "cot_macro";
    if (tab === "microstructure") return "gex_snapshot";
    if (tab === "congressional") return "congressional_trades_sync";
    return undefined;
  })();

  const { status: jobStatus, scanProgress, connected } = useJobUpdates(["jobs"], {
    onJobFinished: (name, status) => {
      if (status !== "ok") return;
      if (name === "smart_money_feed" && tab === "feed") loadFeed();
      if (name === "watchlist_pulse" && tab === "pulse" && pulseMode === "watchlist") loadPulse();
      if (name === "insider_sp500" && tab === "pulse" && pulseMode === "market") loadInsiderScan("sp500");
      if (
        (name === "options_watchlist" || name === "options_sp100" || name === "options_sp500") &&
        tab === "options"
      ) {
        loadScan(optionsUniverse, optionsSignalsOnly);
      }
      if (
        (name === "volume_watchlist" ||
          name === "volume_sp100" ||
          name === "volume_sp500") &&
        tab === "volume"
      ) {
        loadVolumeScan(volumeUniverse, volumeSignalsOnly);
      }
      if (name === "institutional_conviction" && tab === "institutional") {
        fetchInstitutionalConviction({ universe: "sp500" }).then(setInstitutional).catch(() => {});
      }
      if (name === "activist_feed" && tab === "activist") {
        loadActivist(activistFormFilter);
      }
    },
  });

  useEffect(() => {
    loadFeed();
  }, [loadFeed]);

  useEffect(() => {
    syncFeedFromArchive(feedDateRange);
  }, [feedDateRange, syncFeedFromArchive]);

  useEffect(() => {
    if (tab === "activist") {
      loadActivist(activistFormFilter);
    }
  }, [tab, activistFormFilter, loadActivist]);

  useEffect(() => {
    if (tab !== "pulse" || loadingPulse) return;
    if (pulseMode === "watchlist" && pulse.rows.length === 0 && !pulse.message) {
      loadPulse();
    }
    if (pulseMode === "market" && !insiderScan) {
      loadInsiderScan("sp500");
    }
  }, [tab, pulseMode, loadPulse, loadInsiderScan, loadingPulse, pulse.rows.length, pulse.message, insiderScan]);

  useEffect(() => {
    if (tab === "options") loadScan(optionsUniverse, optionsSignalsOnly);
  }, [tab, optionsUniverse, optionsSignalsOnly, loadScan]);

  useEffect(() => {
    if (["institutional", "cot", "microstructure", "congressional"].includes(tab)) {
      loadTabData(tab);
    }
  }, [tab, loadTabData]);

  useEffect(() => {
    if (tab === "volume") loadVolumeScan(volumeUniverse, volumeSignalsOnly);
  }, [tab, volumeUniverse, volumeSignalsOnly, loadVolumeScan]);

  const tabs: { id: Tab; label: string }[] = [
    { id: "feed", label: "Insider feed" },
    { id: "pulse", label: "Insider scan" },
    { id: "institutional", label: "Institutional 13F" },
    { id: "fund", label: "Fund holdings" },
    { id: "activist", label: "Activist stakes" },
    { id: "options", label: "Options" },
    { id: "volume", label: "Volume" },
    { id: "microstructure", label: "Market structure" },
    { id: "congressional", label: "Congressional" },
    { id: "cot", label: "Macro COT" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Smart Money</h1>
        <p className="text-sm text-zinc-400 mt-1 max-w-3xl">
          Open-market insider trades (Forms 3/4/5), full-universe 13F when bulk index is ingested,
          N-PORT fund holdings, options ticks (Polygon), GEX/DIX proxies, dark-pool proxy, and congressional trades.
        </p>
      </div>

      <JobStatusBanner
        jobName={tabJobName}
        status={jobStatus}
        scanProgress={scanProgress}
        connected={connected}
      />

      {error && (
        <div className="rounded border border-red-800 bg-red-950/50 px-4 py-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-b border-zinc-800 pb-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 text-sm rounded-t transition-colors ${
              tab === t.id ? "bg-zinc-800 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "feed" && (
        <div className="space-y-3">
          {(() => {
            const feedJob = jobStatus?.jobs.find((j) => j.name === "smart_money_feed");
            if (feedJob?.status !== "running") return null;
            return (
              <p className="text-sm text-amber-400/90">
                Refreshing insider feed from SEC…
                {feedJob.phase ? ` ${feedJob.phase}` : ""}
              </p>
            );
          })()}
          <SmartMoneyFeedTable
            feed={feed}
            items={feedDisplayItems}
            sideFilter={sideFilter}
            onSideFilter={setSideFilter}
            formTypeFilter={formTypeFilter}
            onFormTypeFilter={setFormTypeFilter}
            openMarketOnly={openMarketOnly}
            onOpenMarketOnly={setOpenMarketOnly}
            dateRange={feedDateRange}
            onDateRangeChange={handleFeedDateRangeChange}
            archiveCount={archiveMeta.count}
            archiveUpdatedAt={archiveMeta.updated_at}
            onClearArchive={handleClearArchive}
            onRefresh={() => loadFeed(true)}
            loading={loadingFeed}
          />
        </div>
      )}

      {tab === "pulse" && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {(
              [
                { id: "market" as const, label: "S&P 500 accumulation" },
                { id: "watchlist" as const, label: "Watchlist pulse" },
              ] as const
            ).map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setPulseMode(m.id)}
                className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                  pulseMode === m.id
                    ? "border-emerald-700 bg-emerald-950/40 text-emerald-300"
                    : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          {pulseMode === "watchlist" ? (
            <WatchlistInsiderPulsePanel pulse={pulse} loading={loadingPulse} />
          ) : (
            <InsiderScanPanel scan={insiderScan} loading={loadingPulse} />
          )}
        </div>
      )}

      {tab === "options" && (
        <OptionsActivityScanPanel
          scan={scan}
          universe={optionsUniverse}
          onUniverse={setOptionsUniverse}
          signalsOnly={optionsSignalsOnly}
          onSignalsOnly={setOptionsSignalsOnly}
          loading={loadingScan}
          bannerMessage={optionsBanner}
        />
      )}

      {tab === "institutional" && (
        <InstitutionalConvictionPanel scan={institutional} loading={loadingOther} />
      )}

      {tab === "fund" && <FundHoldingsPanel loading={loadingOther} />}

      {tab === "activist" && (
        <ActivistFeedPanel
          feed={activist}
          formFilter={activistFormFilter}
          onFormFilter={setActivistFormFilter}
          onRefresh={() => loadActivist(activistFormFilter, true)}
          loading={loadingOther}
        />
      )}

      {tab === "volume" && (
        <VolumeScanPanel
          scan={volumeScan}
          universe={volumeUniverse}
          onUniverse={setVolumeUniverse}
          signalsOnly={volumeSignalsOnly}
          onSignalsOnly={setVolumeSignalsOnly}
          loading={loadingOther}
          bannerMessage={volumeBanner}
        />
      )}

      {tab === "cot" && (
        <div className="space-y-3">
          <p className="text-xs text-zinc-500">
            {cot?.disclaimer ||
              "Macro futures positioning — commercial hedgers vs speculators (CFTC weekly)."}
          </p>
          {loadingOther && <p className="text-sm text-zinc-500">Loading COT data…</p>}
          {cot?.message && <p className="text-sm text-zinc-500">{cot.message}</p>}
          {cot?.positions && cot.positions.length > 0 && (
            <ul className="text-sm space-y-2">
              {cot.positions.map((p) => (
                <li key={p.symbol} className="border border-zinc-800 rounded px-3 py-2">
                  <span className="font-mono text-emerald-400">{p.symbol}</span>
                  <span className="text-zinc-400 ml-2">{p.market_name}</span>
                  {p.commercial_net != null && (
                    <span className="text-zinc-300 ml-2">
                      commercial net: {p.commercial_net.toLocaleString()}
                    </span>
                  )}
                  {p.reversal_zone && (
                    <span className="text-amber-400 ml-2 text-xs">reversal zone</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {tab === "microstructure" && (
        <MicrostructurePanel data={microstructure} loading={loadingOther} />
      )}

      {tab === "congressional" && (
        <CongressionalPanel feed={congressional} loading={loadingOther} />
      )}
    </div>
  );
}
