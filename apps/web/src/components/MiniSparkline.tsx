"use client";

import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { ContextVisualSparkPoint } from "@/lib/api";

type Props = {
  data: ContextVisualSparkPoint[];
  valueSuffix?: string;
};

export function MiniSparkline({ data, valueSuffix = "" }: Props) {
  if (data.length < 2) return null;

  const chartData = data.map((d) => ({
    period: d.period,
    value: d.value,
  }));

  return (
    <div className="h-[72px] w-full mt-2">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <Tooltip
            contentStyle={{
              background: "#18181b",
              border: "1px solid #3f3f46",
              borderRadius: 6,
              fontSize: 11,
            }}
            formatter={(value) => {
              const n = typeof value === "number" ? value : Number(value);
              const text = Number.isFinite(n) ? `${n.toFixed(1)}${valueSuffix}` : "—";
              return [text, ""];
            }}
            labelFormatter={(label) => String(label)}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="#34d399"
            strokeWidth={1.5}
            dot={{ r: 2, fill: "#34d399" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
