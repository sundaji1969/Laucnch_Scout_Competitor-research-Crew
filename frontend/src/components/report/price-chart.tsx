"use client";

import {
  CartesianGrid,
  ErrorBar,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { Strategy } from "@/lib/api";
import { chartPrice } from "@/lib/price";

interface Point {
  name: string;
  price: number;
  /** Ends of a published price range, drawn as a horizontal bar. */
  low?: number;
  high?: number;
  /** [below, above] the plotted price, for Recharts' ErrorBar; absent for single prices. */
  range?: [number, number];
  diff: number;
  label: string;
}

export function PriceChart({ strategy }: { strategy: Strategy }) {
  const points: Point[] = [];
  let unpriced = 0;
  for (const r of strategy.matrix) {
    const p = chartPrice(r.price_value, r.price_per_unit);
    if (!p) {
      unpriced += 1;
      continue;
    }
    points.push({
      name: r.competitor,
      price: p.value,
      low: p.low,
      high: p.high,
      range: p.low !== undefined && p.high !== undefined ? [p.value - p.low, p.high - p.value] : undefined,
      diff: r.differentiation_score,
      label: r.price_per_unit,
    });
  }
  const hasRange = points.some((p) => p.low !== undefined);
  const rec = strategy.recommended_price_value ?? undefined;

  if (points.length < 2) {
    return (
      <p className="text-sm text-muted">
        Not enough published prices to chart. {unpriced} of {strategy.matrix.length} competitors don&apos;t
        list a price publicly, which may itself be an opening for transparent pricing.
      </p>
    );
  }

  const maxPrice = Math.max(...points.map((p) => p.high ?? p.price), rec ?? 0);
  // Nudge labels of points that sit close together so names never overprint each other.
  const sorted = [...points].sort((a, b) => a.price - b.price || a.diff - b.diff);
  // Greedy label placement: each label takes the first vertical offset that doesn't overlap a label
  // already placed nearby (≈24px per differentiation point on a 280px chart; labels are ~16px tall).
  const PX_PER_POINT = 23;
  const placed: { price: number; y: number }[] = [];
  const labelled = sorted.map((p) => {
    const short = p.name.length > 22 ? `${p.name.slice(0, 20)}…` : p.name;
    const candidates = [0, -16, 16, -32, 32, -48, 48];
    const dy =
      candidates.find((off) => {
        const y = p.diff * PX_PER_POINT - off;
        return !placed.some((q) => Math.abs(q.price - p.price) < maxPrice * 0.2 && Math.abs(q.y - y) < 15);
      }) ?? 0;
    placed.push({ price: p.price, y: p.diff * PX_PER_POINT - dy });
    return { ...p, short, dy };
  });
  return (
    <figure>
      <div
        className="h-[280px] w-full"
        role="img"
        aria-label={`Price versus differentiation for ${points.length} competitors${rec ? `, with the recommended price of ${strategy.recommended_price}` : ""}.`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 16, right: 24, bottom: 28, left: 8 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" />
            <XAxis
              type="number"
              dataKey="price"
              name="Price"
              domain={[0, Math.ceil((maxPrice * 1.15) / 100) * 100]}
              tick={{ fill: "var(--fg-muted)", fontSize: 12 }}
              tickFormatter={(v) => `₹${Number(v).toLocaleString("en-IN")}`}
              stroke="var(--border-strong)"
              label={{ value: "Price per unit", position: "insideBottom", offset: -16, fill: "var(--fg-muted)", fontSize: 12 }}
            />
            <YAxis
              type="number"
              dataKey="diff"
              name="Differentiation"
              domain={[0, 10]}
              ticks={[0, 5, 10]}
              tick={{ fill: "var(--fg-muted)", fontSize: 12 }}
              stroke="var(--border-strong)"
              width={44}
              label={{ value: "Differentiation", angle: -90, position: "insideLeft", offset: 14, fill: "var(--fg-muted)", fontSize: 12 }}
            />
            <ZAxis range={[90, 90]} />
            {rec && (
              <ReferenceLine
                x={rec}
                stroke="var(--accent)"
                strokeDasharray="4 3"
                label={{ value: `You: ₹${rec.toLocaleString("en-IN")}`, position: "top", fill: "var(--accent-strong)", fontSize: 12 }}
              />
            )}
            <Tooltip
              cursor={{ strokeDasharray: "3 3", stroke: "var(--border-strong)" }}
              content={({ payload }) => {
                const p = payload?.[0]?.payload as Point | undefined;
                if (!p) return null;
                return (
                  <div className="rounded-lg border border-border bg-elevated px-3 py-2 text-xs shadow-soft">
                    <p className="font-medium">{p.name}</p>
                    <p className="text-muted">{p.label}</p>
                    <p className="text-muted">Differentiation {p.diff}/10</p>
                  </div>
                );
              }}
            />
            <Scatter
              data={labelled}
              isAnimationActive={false}
              shape={(props: unknown) => {
                // Point + label drawn together so the collision offset (dy) is applied reliably.
                const { cx, cy, payload } = props as { cx: number; cy: number; payload: (typeof labelled)[number] };
                return (
                  <g>
                    <circle cx={cx} cy={cy} r={5} fill="var(--chart-2)" />
                    {/* A range bar runs through the space to the right, so its label sits above the point. */}
                    <text
                      x={payload.range ? cx : cx + 9}
                      y={payload.range ? cy - 13 : cy + payload.dy}
                      fontSize={12}
                      fill="var(--fg)"
                      dominantBaseline="middle"
                      textAnchor={payload.range ? "middle" : "start"}
                    >
                      {payload.short}
                    </text>
                  </g>
                );
              }}
            >
              {hasRange && (
                <ErrorBar dataKey="range" direction="x" isAnimationActive={false} width={6} strokeWidth={2} stroke="var(--chart-2)" strokeOpacity={0.55} />
              )}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-2 text-[13px] text-muted">
        Differentiation scores are the Strategy Analyst&apos;s judgement (1 = commodity, 10 = highly distinct).
        {hasRange && " Price ranges are plotted at their midpoint, with a bar showing the range."}
        {unpriced > 0 && ` ${unpriced} competitor${unpriced > 1 ? "s" : ""} without a public price ${unpriced > 1 ? "are" : "is"} not plotted.`}
      </figcaption>
    </figure>
  );
}
