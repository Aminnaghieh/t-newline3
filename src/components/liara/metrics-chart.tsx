"use client";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MetricPoint } from "@/lib/liara/types";

const COLORS: Record<string, string> = {
  cpu: "#87fcc4",
  memory: "#28c1f5",
  network: "#ffc000",
  disk: "#00ebc9",
};

function faTime(t: number) {
  return new Date(t * 1000).toLocaleTimeString("fa-IR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MetricsChart({
  points,
  unit,
  metric,
  height = 230,
}: {
  points: MetricPoint[];
  unit: string;
  metric: string;
  height?: number;
}) {
  const color = COLORS[metric] ?? "#87fcc4";
  const data = points.map((p) => ({ t: p.t, v: p.v }));
  return (
    <div style={{ height }} dir="ltr" className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`grad-${metric}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.32} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis
            dataKey="t"
            tickFormatter={faTime}
            tick={{ fill: "#93a29a", fontSize: 10 }}
            stroke="rgba(255,255,255,0.1)"
            minTickGap={48}
          />
          <YAxis
            tick={{ fill: "#93a29a", fontSize: 10 }}
            stroke="rgba(255,255,255,0.1)"
            width={38}
            domain={[0, metric === "network" ? "auto" : 100]}
            unit={metric === "network" ? "" : "%"}
          />
          <Tooltip
            contentStyle={{
              background: "#202723",
              border: "1px solid rgba(255,255,255,0.12)",
              borderRadius: 12,
              fontSize: 12,
              fontFamily: "Vazirmatn, Tahoma",
            }}
            labelStyle={{ color: "#93a29a" }}
            labelFormatter={(t) => faTime(Number(t))}
            formatter={(v: number) => [`${v} ${unit}`, "مصرف"]}
          />
          <Area
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={2}
            fill={`url(#grad-${metric})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
