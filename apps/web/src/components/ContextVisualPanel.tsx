"use client";

import type { ContextSummary, ContextVisualSnapshot } from "@/lib/api";
import {
  mapBulletsToSections,
  shouldCollapseSectionCard,
} from "@/lib/contextBulletMap";
import { metricToneClass, stanceDotClass, stancePillClass } from "@/lib/stanceStyles";
import { MiniSparkline } from "@/components/MiniSparkline";

type Props = {
  visuals: ContextVisualSnapshot;
  summary: ContextSummary;
};

export function ContextVisualPanel({ visuals, summary }: Props) {
  const bullets = summary.bullets;
  const labels = summary.section_labels ?? [];
  const { paired, orphanBullets } = mapBulletsToSections(
    visuals.sections,
    bullets,
    labels,
    summary.section_bullets
  );

  const visiblePaired = paired.filter(
    (item) => !shouldCollapseSectionCard(item.section, item.bullet)
  );

  return (
    <div className="space-y-5">
      <div>
        <h4 className="text-xs font-medium text-zinc-400 mb-2">Summary pillars</h4>
        <div className="flex flex-wrap gap-2">
          {visuals.pillars.map((pillar) => (
            <span
              key={pillar.id}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${stancePillClass(pillar.stance)}`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full shrink-0 ${stanceDotClass(pillar.stance)}`}
              />
              {pillar.label}
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {visiblePaired.map(({ section, bullet, label }) => {
          const sparkSuffix =
            section.id === "growth" ? "%" : section.id === "balance_sheet" ? "" : "";

          return (
            <article
              key={section.id}
              className="rounded-lg border border-zinc-800/80 bg-zinc-950/40 p-4 space-y-2"
            >
              <div className="flex items-start gap-2">
                <span
                  className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${stanceDotClass(section.stance)}`}
                  title={section.stance}
                />
                <div className="min-w-0 flex-1">
                  <h5 className="text-sm font-medium text-zinc-200">{section.title}</h5>
                  {label?.headline && label.headline !== "Data Unavailable" && (
                    <p className="text-xs text-zinc-500 mt-0.5">{label.headline}</p>
                  )}
                </div>
              </div>

              {section.metrics.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {section.metrics.map((m, idx) => (
                    <span
                      key={`${m.label}-${idx}`}
                      className="rounded border border-zinc-800 bg-zinc-900/60 px-2 py-1 text-xs"
                    >
                      <span className="text-zinc-500">{m.label}: </span>
                      <span className={`font-mono ${metricToneClass(m.tone)}`}>{m.value}</span>
                    </span>
                  ))}
                </div>
              )}

              {section.sparkline.length >= 2 && (
                <MiniSparkline data={section.sparkline} valueSuffix={sparkSuffix} />
              )}

              {bullet && (
                <p className="text-sm text-zinc-300 leading-relaxed border-t border-zinc-800/60 pt-2 mt-2">
                  {bullet}
                </p>
              )}
            </article>
          );
        })}
      </div>

      {orphanBullets.length > 0 && (
        <div className="space-y-2 border-t border-zinc-800/80 pt-3">
          <h4 className="text-xs font-medium text-zinc-500">Additional context</h4>
          {orphanBullets.map((b, i) => (
            <p key={`orphan-${i}`} className="text-sm text-zinc-300 leading-relaxed">
              {b}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
