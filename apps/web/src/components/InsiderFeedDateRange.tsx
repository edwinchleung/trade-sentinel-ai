"use client";

export type FeedDatePreset = "today" | "7d" | "30d" | "custom";

export type FeedDateRange = {
  preset: FeedDatePreset;
  start: string;
  end: string;
};

/** Format a Date as YYYY-MM-DD in the user's local calendar (not UTC). */
export function localCalendarIso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function todayIso() {
  return localCalendarIso(new Date());
}

export function rangeFromPreset(preset: FeedDatePreset): { start: string; end: string } {
  const end = new Date();
  const start = new Date(end);
  if (preset === "today") {
    /* start = end */
  } else if (preset === "7d") {
    start.setDate(start.getDate() - 6);
  } else if (preset === "30d") {
    start.setDate(start.getDate() - 29);
  }
  return { start: localCalendarIso(start), end: localCalendarIso(end) };
}

type Props = {
  range: FeedDateRange;
  onChange: (range: FeedDateRange) => void;
  maxSpanDays?: number;
};

const PRESETS: { id: FeedDatePreset; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "7d", label: "Last 7 days" },
  { id: "30d", label: "Last 30 days" },
  { id: "custom", label: "Custom" },
];

export function InsiderFeedDateRange({ range, onChange, maxSpanDays = 30 }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {PRESETS.map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={() => {
            if (p.id === "custom") {
              onChange({ ...range, preset: "custom" });
              return;
            }
            const { start, end } = rangeFromPreset(p.id);
            onChange({ preset: p.id, start, end });
          }}
          className={`rounded-full border px-3 py-1 text-xs transition-colors ${
            range.preset === p.id
              ? "border-emerald-700 bg-emerald-950/40 text-emerald-300"
              : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
          }`}
        >
          {p.label}
        </button>
      ))}
      {range.preset === "custom" && (
        <>
          <input
            type="date"
            value={range.start}
            max={range.end}
            onChange={(e) => onChange({ ...range, start: e.target.value, preset: "custom" })}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-300"
          />
          <span className="text-zinc-600 text-xs">to</span>
          <input
            type="date"
            value={range.end}
            min={range.start}
            max={todayIso()}
            onChange={(e) => onChange({ ...range, end: e.target.value, preset: "custom" })}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-300"
          />
        </>
      )}
      <span className="text-xs text-zinc-600">
        {range.start === range.end ? range.start : `${range.start} → ${range.end}`}
        {maxSpanDays ? ` · max ${maxSpanDays}d per fetch` : ""}
      </span>
    </div>
  );
}
