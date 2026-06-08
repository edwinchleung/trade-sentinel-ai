"use client";

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { OptionsExpiryBreakdown, OptionsFlowFlag } from "@/lib/api";

type Props = {
  flow: OptionsFlowFlag;
};

export function OptionsFlowChart({ flow }: Props) {
  const data = [
    { name: "Calls", volume: flow.call_volume ?? 0, fill: "#34d399" },
    { name: "Puts", volume: flow.put_volume ?? 0, fill: "#f87171" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center text-xs text-zinc-400 font-mono">
        {flow.expiry && <span>Nearest expiry: {flow.expiry}</span>}
        {flow.put_call_ratio != null && (
          <span>P/C ratio: {flow.put_call_ratio.toFixed(2)}</span>
        )}
        {flow.total_open_interest != null && (
          <span>Total OI: {flow.total_open_interest.toLocaleString()}</span>
        )}
        {flow.unusual && (
          <span className="rounded-full bg-amber-950/60 border border-amber-800 text-amber-300 px-2 py-0.5">
            Unusual activity
          </span>
        )}
      </div>

      {flow.unusual_reason && (
        <p className="text-xs text-amber-400/90">{flow.unusual_reason}</p>
      )}

      {(flow.call_volume != null || flow.put_volume != null) && (
        <div className="h-40 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="#52525b" />
              <YAxis tick={{ fontSize: 10 }} stroke="#52525b" />
              <Tooltip
                formatter={(value) => [
                  typeof value === "number" ? value.toLocaleString() : String(value ?? ""),
                  "Volume",
                ]}
                contentStyle={{
                  background: "#18181b",
                  border: "1px solid #3f3f46",
                  borderRadius: 8,
                }}
              />
              <Bar dataKey="volume" radius={[4, 4, 0, 0]}>
                {data.map((entry) => (
                  <Cell key={entry.name} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {flow.expiry_breakdown && flow.expiry_breakdown.length > 1 && (
        <ExpiryTable breakdown={flow.expiry_breakdown} />
      )}

      {flow.top_strikes && flow.top_strikes.length > 0 && (
        <div>
          <h4 className="text-xs text-zinc-500 uppercase tracking-wide mb-2">
            Top strikes by volume
          </h4>
          <ul className="text-xs font-mono text-zinc-400 space-y-1">
            {flow.top_strikes.map((s, i) => (
              <li key={i}>
                ${s.strike} {s.side} — vol {s.volume.toLocaleString()}
                {s.open_interest > 0 && ` · OI ${s.open_interest.toLocaleString()}`}
              </li>
            ))}
          </ul>
        </div>
      )}

      {flow.message && (
        <p className="text-xs text-zinc-500">{flow.message}</p>
      )}
    </div>
  );
}

function ExpiryTable({ breakdown }: { breakdown: OptionsExpiryBreakdown[] }) {
  return (
    <div>
      <h4 className="text-xs text-zinc-500 uppercase tracking-wide mb-2">
        Term structure
      </h4>
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-zinc-500 text-left">
            <th className="py-1 pr-3">Expiry</th>
            <th className="py-1 pr-3">Calls</th>
            <th className="py-1 pr-3">Puts</th>
            <th className="py-1">P/C</th>
          </tr>
        </thead>
        <tbody className="text-zinc-400">
          {breakdown.map((row) => (
            <tr key={row.expiry} className="border-t border-zinc-800/50">
              <td className="py-1 pr-3">{row.expiry}</td>
              <td className="py-1 pr-3">{row.call_volume.toLocaleString()}</td>
              <td className="py-1 pr-3">{row.put_volume.toLocaleString()}</td>
              <td className="py-1">
                {row.put_call_ratio != null ? row.put_call_ratio.toFixed(2) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
