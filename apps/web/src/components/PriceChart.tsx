"use client";

import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Point = { date: string; close: number };

type Props = {
  data: Point[];
  sma20?: number | null;
  sma50?: number | null;
};

export function PriceChart({ data, sma20, sma50 }: Props) {
  if (!data.length) return null;
  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="#52525b" />
          <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10 }} stroke="#52525b" />
          <Tooltip
            contentStyle={{
              background: "#18181b",
              border: "1px solid #3f3f46",
              borderRadius: 8,
            }}
          />
          {sma20 != null && (
            <ReferenceLine
              y={sma20}
              stroke="#60a5fa"
              strokeDasharray="4 4"
              label={{ value: "SMA20", fill: "#60a5fa", fontSize: 10 }}
            />
          )}
          {sma50 != null && (
            <ReferenceLine
              y={sma50}
              stroke="#a78bfa"
              strokeDasharray="4 4"
              label={{ value: "SMA50", fill: "#a78bfa", fontSize: 10 }}
            />
          )}
          <Line
            type="monotone"
            dataKey="close"
            stroke="#34d399"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
