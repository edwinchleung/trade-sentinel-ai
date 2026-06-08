import type { FundamentalAssessment } from "@/lib/api";

const LABEL_COLORS: Record<string, string> = {
  favorable: "text-emerald-400",
  strong: "text-emerald-400",
  bullish: "text-emerald-400",
  cheap: "text-emerald-400",
  neutral: "text-zinc-300",
  adequate: "text-zinc-300",
  fair: "text-zinc-300",
  mixed: "text-amber-400",
  caution: "text-amber-400",
  weak: "text-amber-400",
  bearish: "text-red-400",
  rich: "text-amber-400",
};

export function FundamentalAssessmentCard({
  assessment,
}: {
  assessment: FundamentalAssessment;
}) {
  if (!assessment.data_available) {
    return (
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
        <h3 className="text-sm font-medium text-zinc-300">Fundamental assessment</h3>
        <p className="mt-2 text-sm text-zinc-500">
          {assessment.message ?? "Fundamental assessment unavailable."}
        </p>
      </section>
    );
  }

  const rows = [
    { label: "Quality", value: assessment.quality_label },
    { label: "Growth", value: assessment.growth_label },
    { label: "Balance sheet", value: assessment.balance_sheet_label },
    { label: "Valuation context", value: assessment.valuation_context_label },
  ].filter((r) => r.value);

  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-emerald-400">Fundamental assessment</h3>
        {assessment.overall_label && (
          <span
            className={`text-xs rounded border border-zinc-700 px-2 py-0.5 capitalize ${LABEL_COLORS[assessment.overall_label] ?? "text-zinc-400"}`}
          >
            {assessment.overall_label}
          </span>
        )}
      </div>

      {assessment.summary && (
        <p className="text-sm text-zinc-300 leading-relaxed">{assessment.summary}</p>
      )}

      {rows.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          {rows.map((r) => (
            <div key={r.label}>
              <p className="text-zinc-500 text-xs">{r.label}</p>
              <p className={`capitalize ${LABEL_COLORS[r.value ?? ""] ?? "text-zinc-300"}`}>
                {r.value}
              </p>
            </div>
          ))}
        </div>
      )}

      {assessment.highlights && assessment.highlights.length > 0 && (
        <ul className="space-y-1 text-sm text-zinc-300 list-disc list-inside">
          {assessment.highlights.map((h) => (
            <li key={h}>{h}</li>
          ))}
        </ul>
      )}

      {assessment.signals && assessment.signals.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {assessment.signals.map((sig) => (
            <span
              key={sig}
              className="text-xs rounded border border-zinc-700 bg-zinc-950/60 px-2 py-0.5 text-zinc-400 font-mono"
            >
              {sig}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
