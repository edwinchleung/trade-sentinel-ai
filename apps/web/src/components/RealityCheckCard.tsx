import type { RealityCheck, ContextSummary } from "@/lib/api";

const BIAS_COLORS: Record<string, string> = {
  constructive: "text-emerald-400 border-emerald-800",
  cautious: "text-amber-400 border-amber-800",
  mixed: "text-zinc-300 border-zinc-700",
  unavailable: "text-zinc-500 border-zinc-700",
};

export function RealityCheckCard({
  realityCheck,
  summary,
}: {
  realityCheck: RealityCheck;
  summary?: ContextSummary | null;
}) {
  if (!realityCheck.data_available) {
    return null;
  }

  const bias = realityCheck.overall_bias ?? "mixed";
  const narrative =
    summary?.reality_check_narrative ?? realityCheck.headline ?? "";

  return (
    <section className="rounded-lg border border-violet-900/40 bg-violet-950/20 p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-violet-300">Pre-trade reality check</h3>
        <div className="flex items-center gap-2">
          <span
            className={`text-xs rounded border px-2 py-0.5 capitalize ${BIAS_COLORS[bias] ?? BIAS_COLORS.mixed}`}
          >
            {bias}
          </span>
          {realityCheck.confidence && (
            <span className="text-xs text-zinc-500 capitalize">
              {realityCheck.confidence} confidence
            </span>
          )}
        </div>
      </div>

      {narrative && (
        <p className="text-sm text-zinc-200 leading-relaxed">{narrative}</p>
      )}

      <div className="grid sm:grid-cols-3 gap-4 text-sm">
        {realityCheck.key_catalysts && realityCheck.key_catalysts.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-emerald-500/80 mb-1">Catalysts</h4>
            <ul className="space-y-1 text-zinc-300 text-xs list-disc list-inside">
              {realityCheck.key_catalysts.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        )}
        {realityCheck.key_risks && realityCheck.key_risks.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-amber-500/80 mb-1">Risks</h4>
            <ul className="space-y-1 text-zinc-300 text-xs list-disc list-inside">
              {realityCheck.key_risks.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        )}
        {realityCheck.invalidation_triggers &&
          realityCheck.invalidation_triggers.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-sky-500/80 mb-1">What would change the view</h4>
              <ul className="space-y-1 text-zinc-300 text-xs list-disc list-inside">
                {realityCheck.invalidation_triggers.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
          )}
      </div>

      {summary?.scenario_bullets && summary.scenario_bullets.length > 0 && (
        <div className="grid sm:grid-cols-3 gap-2 pt-2 border-t border-zinc-800">
          {summary.scenario_bullets.map((s, i) => (
            <div
              key={i}
              className="rounded border border-zinc-800 bg-zinc-950/40 p-3 text-xs text-zinc-300 leading-relaxed"
            >
              {s}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
