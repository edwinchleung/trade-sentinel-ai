"use client";

type Props = {
  disclaimer?: string | null;
  meta?: string | null;
  loading?: boolean;
  loadingLabel?: string;
  message?: string | null;
  messageTone?: "muted" | "warn";
  degradedMessage?: string | null;
  partialHint?: string | null;
};

export function SmartMoneyPanelMeta({
  disclaimer,
  meta,
  loading,
  loadingLabel = "Loading…",
  message,
  messageTone = "muted",
  degradedMessage,
  partialHint,
}: Props) {
  return (
    <>
      {disclaimer && <p className="text-xs text-zinc-500">{disclaimer}</p>}
      {loading && <p className="text-sm text-zinc-500">{loadingLabel}</p>}
      {!loading && meta && <p className="text-xs text-zinc-500">{meta}</p>}
      {degradedMessage && (
        <p className="text-sm text-amber-400/90">{degradedMessage}</p>
      )}
      {partialHint && <p className="text-xs text-amber-400/80">{partialHint}</p>}
      {!loading && message && (
        <p
          className={`text-sm ${
            messageTone === "warn" ? "text-amber-400/90" : "text-zinc-500"
          }`}
        >
          {message}
        </p>
      )}
    </>
  );
}
