"use client";

type Props = {
  notable?: boolean;
  cluster?: boolean;
  conviction?: boolean;
};

export function SignalPills({ notable, cluster, conviction }: Props) {
  if (!notable && !cluster && !conviction) return <span className="text-zinc-600">—</span>;
  return (
    <span className="inline-flex flex-wrap gap-1">
      {conviction && (
        <span className="rounded-full border border-emerald-800 bg-emerald-950/50 px-2 py-0.5 text-[10px] text-emerald-300">
          Conviction
        </span>
      )}
      {notable && (
        <span className="rounded-full border border-amber-800 bg-amber-950/40 px-2 py-0.5 text-[10px] text-amber-300">
          Notable
        </span>
      )}
      {cluster && (
        <span className="rounded-full border border-sky-800 bg-sky-950/40 px-2 py-0.5 text-[10px] text-sky-300">
          Cluster
        </span>
      )}
    </span>
  );
}
