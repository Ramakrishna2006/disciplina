import { useId, useState, type PointerEvent } from "react"

import { cn } from "@/lib/utils"

/**
 * A line chart drawn as plain SVG (no chart library: one less dependency, and it is small).
 *
 *  - Lines are 2 px, colours come from the --series-N tokens in index.css, in a fixed order.
 *  - Moving the pointer (or finger) over the chart shows a crosshair and the values at that step.
 *  - Colour is never the only clue: there is always a legend, dashed lines can mark a second
 *    kind of value, and "Show as table" lists the numbers for screen readers and printing.
 */
export interface Series {
  name: string
  points: { x: number; y: number }[]
  /** 1-4: which --series-N colour. Keep the same number for the same thing on every chart. */
  color: 1 | 2 | 3 | 4
  dashed?: boolean
}

const W = 640
const H = 260
const PAD = { top: 12, right: 16, bottom: 34, left: 48 }

function niceTicks(min: number, max: number, count = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return []
  if (min === max) return [min]
  const raw = (max - min) / count
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw
  const ticks: number[] = []
  for (let t = Math.ceil(min / step) * step; t <= max + step * 1e-9; t += step) ticks.push(Number(t.toFixed(10)))
  return ticks
}

function fmt(n: number) {
  return Math.abs(n) >= 1000 ? n.toLocaleString() : Number(n.toFixed(3)).toString()
}

export function LossChart({
  series,
  xLabel = "step",
  yLabel = "loss",
  title,
  className,
}: {
  series: Series[]
  xLabel?: string
  yLabel?: string
  title: string
  className?: string
}) {
  const id = useId()
  const [hoverX, setHoverX] = useState<number | null>(null)
  const [showTable, setShowTable] = useState(false)
  const visible = series.filter((s) => s.points.length > 0)

  if (visible.length === 0) {
    return (
      <div className={cn("flex h-48 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground", className)}>
        No points yet.
      </div>
    )
  }

  const xs = visible.flatMap((s) => s.points.map((p) => p.x))
  const ys = visible.flatMap((s) => s.points.map((p) => p.y))
  const xMin = Math.min(...xs)
  const xMax = Math.max(...xs)
  const pad = (Math.max(...ys) - Math.min(...ys) || 1) * 0.06
  const yMin = Math.max(0, Math.min(...ys) - pad)
  const yMax = Math.max(...ys) + pad
  const plotW = W - PAD.left - PAD.right
  const plotH = H - PAD.top - PAD.bottom
  const sx = (x: number) => PAD.left + (xMax === xMin ? plotW / 2 : ((x - xMin) / (xMax - xMin)) * plotW)
  const sy = (y: number) => PAD.top + (1 - (y - yMin) / (yMax - yMin || 1)) * plotH
  const xTicks = niceTicks(xMin, xMax, 6)
  const yTicks = niceTicks(yMin, yMax, 4)

  function nearest(points: Series["points"], x: number) {
    let best = points[0]
    for (const p of points) if (Math.abs(p.x - x) < Math.abs(best.x - x)) best = p
    return best
  }

  function onMove(e: PointerEvent<SVGSVGElement>) {
    const box = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - box.left) / box.width) * W
    const x = xMin + ((px - PAD.left) / plotW) * (xMax - xMin)
    setHoverX(Math.min(xMax, Math.max(xMin, x)))
  }

  const hover = hoverX === null ? null : visible.map((s) => ({ s, p: nearest(s.points, hoverX) }))
  const hoverStep = hover ? hover[0].p.x : null
  const summary = visible
    .map((s) => `${s.name}: from ${fmt(s.points[0].y)} to ${fmt(s.points[s.points.length - 1].y)}`)
    .join("; ")

  return (
    <figure className={cn("grid gap-3", className)}>
      <div className="relative">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-auto w-full touch-pan-y select-none"
          role="img"
          aria-labelledby={`${id}-title`}
          aria-describedby={`${id}-desc`}
          onPointerMove={onMove}
          onPointerLeave={() => setHoverX(null)}
        >
          <title id={`${id}-title`}>{title}</title>
          <desc id={`${id}-desc`}>{summary}</desc>
          {yTicks.map((t) => (
            <g key={`y${t}`}>
              <line x1={PAD.left} x2={W - PAD.right} y1={sy(t)} y2={sy(t)} className="stroke-border" strokeWidth={1} />
              <text x={PAD.left - 8} y={sy(t)} dy="0.32em" textAnchor="end" className="fill-muted-foreground text-[11px]">
                {fmt(t)}
              </text>
            </g>
          ))}
          {xTicks.map((t) => (
            <text key={`x${t}`} x={sx(t)} y={H - PAD.bottom + 16} textAnchor="middle" className="fill-muted-foreground text-[11px]">
              {fmt(t)}
            </text>
          ))}
          <text x={PAD.left + plotW / 2} y={H - 4} textAnchor="middle" className="fill-muted-foreground text-[11px]">
            {xLabel}
          </text>
          <text
            transform={`translate(12 ${PAD.top + plotH / 2}) rotate(-90)`}
            textAnchor="middle"
            className="fill-muted-foreground text-[11px]"
          >
            {yLabel}
          </text>
          {visible.map((s) => (
            <polyline
              key={s.name}
              fill="none"
              stroke={`var(--series-${s.color})`}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              strokeDasharray={s.dashed ? "6 4" : undefined}
              points={s.points.map((p) => `${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join(" ")}
            />
          ))}
          {hover && hoverStep !== null && (
            <g aria-hidden>
              <line x1={sx(hoverStep)} x2={sx(hoverStep)} y1={PAD.top} y2={PAD.top + plotH} className="stroke-muted-foreground" strokeWidth={1} />
              {hover.map(({ s, p }) => (
                <circle
                  key={s.name}
                  cx={sx(p.x)}
                  cy={sy(p.y)}
                  r={4}
                  fill={`var(--series-${s.color})`}
                  className="stroke-card"
                  strokeWidth={2}
                />
              ))}
            </g>
          )}
        </svg>
        {hover && hoverStep !== null && (
          <div
            className="pointer-events-none absolute top-2 rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md"
            style={sx(hoverStep) > W / 2 ? { left: 56 } : { right: 16 }}
          >
            <div className="mb-1 font-medium">
              {xLabel} {fmt(hoverStep)}
            </div>
            {hover.map(({ s, p }) => (
              <div key={s.name} className="flex items-center gap-2">
                <span className="inline-block h-0.5 w-3" style={{ background: `var(--series-${s.color})` }} aria-hidden />
                <span className="text-muted-foreground">{s.name}</span>
                <span className="ml-auto pl-3 font-mono tabular-nums">{fmt(p.y)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        {visible.length > 1 &&
          visible.map((s) => (
            <span key={s.name} className="flex items-center gap-2 text-muted-foreground">
              <svg width="18" height="6" aria-hidden>
                <line
                  x1="1"
                  x2="17"
                  y1="3"
                  y2="3"
                  stroke={`var(--series-${s.color})`}
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeDasharray={s.dashed ? "4 3" : undefined}
                />
              </svg>
              {s.name}
            </span>
          ))}
        <button
          type="button"
          className="ml-auto rounded-sm text-sm text-primary underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50"
          onClick={() => setShowTable((v) => !v)}
          aria-expanded={showTable}
        >
          {showTable ? "Hide table" : "Show as table"}
        </button>
      </figcaption>

      {showTable && <ChartTable series={visible} xLabel={xLabel} />}
    </figure>
  )
}

function ChartTable({ series, xLabel }: { series: Series[]; xLabel: string }) {
  const steps = [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b)
  const lookup = series.map((s) => new Map(s.points.map((p) => [p.x, p.y])))
  return (
    <div className="max-h-72 overflow-auto rounded-md border">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-muted">
          <tr>
            <th className="px-3 py-1.5 text-left font-medium">{xLabel}</th>
            {series.map((s) => (
              <th key={s.name} className="px-3 py-1.5 text-right font-medium">
                {s.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="font-mono tabular-nums">
          {steps.map((x) => (
            <tr key={x} className="border-t">
              <td className="px-3 py-1">{x}</td>
              {lookup.map((m, i) => (
                <td key={series[i].name} className="px-3 py-1 text-right">
                  {m.has(x) ? fmt(m.get(x)!) : ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Metrics from the API -> chart series. Pre-training: train (solid) and validation (dashed). */
export function lossSeries(
  metrics: { phase: string; step: number; train_loss: number; val_loss: number | null }[],
  phase: "pretrain" | "finetune"
): Series[] {
  if (phase === "pretrain") {
    const pre = metrics.filter((m) => m.phase === "pretrain")
    return [
      { name: "train", color: 1, points: pre.map((m) => ({ x: m.step, y: m.train_loss })) },
      {
        name: "validation",
        color: 2,
        dashed: true,
        points: pre.filter((m) => m.val_loss !== null).map((m) => ({ x: m.step, y: m.val_loss! })),
      },
    ]
  }
  return [
    { name: "Full fine-tune", color: 3, points: metrics.filter((m) => m.phase === "full").map((m) => ({ x: m.step, y: m.train_loss })) },
    { name: "LoRA", color: 4, points: metrics.filter((m) => m.phase === "lora").map((m) => ({ x: m.step, y: m.train_loss })) },
  ]
}
