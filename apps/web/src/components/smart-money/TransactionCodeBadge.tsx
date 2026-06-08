"use client";

const labels: Record<string, string> = {
  P: "Purchase",
  S: "Sale",
  A: "Grant",
  M: "Exercise",
  G: "Gift",
  F: "Tax",
};

type Props = {
  code?: string | null;
  transactionType?: string | null;
};

export function TransactionCodeBadge({ code, transactionType }: Props) {
  const c = (code ?? "").toUpperCase().slice(0, 1);
  const label = labels[c] ?? transactionType ?? "Form 4";
  const tone =
    c === "P"
      ? "border-emerald-800 text-emerald-300 bg-emerald-950/40"
      : c === "S"
        ? "border-red-800 text-red-300 bg-red-950/40"
        : "border-zinc-700 text-zinc-400 bg-zinc-900/60";

  return (
    <span className="inline-flex items-center gap-1.5">
      {c && (
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-mono ${tone}`}>
          {c}
        </span>
      )}
      <span className="text-zinc-400">{label}</span>
    </span>
  );
}
