"use client";

import { motion } from "framer-motion";
import { useMemo } from "react";

/** Smooth line chart over a normalized series. */
export function LineChart({
  data,
  color = "#3b82f6",
  fill = true,
  height = 120,
}: {
  data: number[];
  color?: string;
  fill?: boolean;
  height?: number;
}) {
  const { path, area } = useMemo(() => {
    const w = 300;
    const h = height;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const span = max - min || 1;
    const pts = data.map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / span) * (h - 12) - 6;
      return [x, y] as const;
    });
    const d = pts
      .map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`))
      .join(" ");
    const a = `${d} L${w},${h} L0,${h} Z`;
    return { path: d, area: a };
  }, [data, height]);

  const id = useMemo(() => `g${Math.random().toString(36).slice(2, 8)}`, []);

  return (
    <svg viewBox={`0 0 300 ${height}`} className="h-full w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.28" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={area} fill={`url(#${id})`} />}
      <motion.path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0 }}
        whileInView={{ pathLength: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 1.1, ease: "easeInOut" }}
      />
    </svg>
  );
}

/** Small field heatmap grid. */
export function Heatmap({ grid }: { grid: number[][] }) {
  return (
    <div
      className="grid gap-[3px]"
      style={{ gridTemplateColumns: `repeat(${grid[0].length}, minmax(0,1fr))` }}
    >
      {grid.flatMap((row, r) =>
        row.map((v, c) => {
          // blue -> cyan -> amber -> red
          const hue = 220 - v * 200;
          return (
            <motion.div
              key={`${r}-${c}`}
              className="aspect-square rounded-[3px]"
              style={{ background: `hsl(${hue} 80% ${28 + v * 34}%)` }}
              initial={{ opacity: 0, scale: 0.6 }}
              whileInView={{ opacity: 0.92, scale: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: (r * grid[0].length + c) * 0.004 }}
            />
          );
        }),
      )}
    </div>
  );
}

/** Animated radial score gauge. */
export function ScoreRing({
  value,
  label,
  color = "#3b82f6",
}: {
  value: number;
  label: string;
  color?: string;
}) {
  const r = 34;
  const circ = 2 * Math.PI * r;
  const offset = circ - (value / 100) * circ;
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-24 w-24">
        <svg viewBox="0 0 80 80" className="h-full w-full -rotate-90">
          <circle cx="40" cy="40" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
          <motion.circle
            cx="40"
            cy="40"
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={circ}
            initial={{ strokeDashoffset: circ }}
            whileInView={{ strokeDashoffset: offset }}
            viewport={{ once: true }}
            transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-semibold text-white">{value}</span>
        </div>
      </div>
      <span className="text-xs text-white/50">{label}</span>
    </div>
  );
}
