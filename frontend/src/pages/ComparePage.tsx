import { Link, useSearchParams } from "react-router"
import { GitCompareIcon } from "lucide-react"

import { LossChart, type Series } from "@/components/LossChart"
import { EmptyState, ErrorState, LoadingRows, PageHeader } from "@/components/PageState"
import { StatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useApi } from "@/hooks/useApi"
import { MODEL_LABELS, formatNumber, formatPercent } from "@/lib/format"
import { api } from "@/services/api"
import type { Experiment, Metric, ModelId } from "@/types/api"

const COLORS = [1, 2, 3, 4] as const

function parseIds(text: string | null): number[] {
  return [...new Set((text ?? "").split(",").map(Number).filter((n) => Number.isInteger(n) && n > 0))].slice(0, 4)
}

function result(e: Experiment, model: ModelId) {
  return e.results?.find((r) => r.model === model)
}

/** A row per measurement, a column per experiment; the best value in each row is marked. */
function ResultsTable({ experiments }: { experiments: Experiment[] }) {
  const rows: { label: string; get: (e: Experiment) => number | undefined; fmt: (n: number) => string; best: "max" | "min" }[] = []
  for (const model of ["lora", "full", "base"] as const) {
    rows.push({ label: `${MODEL_LABELS[model]}: held-out Q&A`, get: (e) => result(e, model)?.qa_heldout, fmt: formatPercent, best: "max" })
  }
  rows.push(
    { label: "LoRA: seen Q&A", get: (e) => result(e, "lora")?.qa_seen, fmt: formatPercent, best: "max" },
    { label: "LoRA: completion", get: (e) => result(e, "lora")?.completion, fmt: formatPercent, best: "max" },
    { label: "LoRA: perplexity", get: (e) => result(e, "lora")?.perplexity, fmt: (n) => n.toFixed(2), best: "min" },
    { label: "Base: perplexity", get: (e) => result(e, "base")?.perplexity, fmt: (n) => n.toFixed(2), best: "min" }
  )
  const settings: [string, (e: Experiment) => string][] = [
    ["Steps (pre + fine)", (e) => `${formatNumber(e.pretrain_steps)} + ${formatNumber(e.finetune_steps)}`],
    ["LoRA rank", (e) => String(e.lora_rank)],
    ["Replay", (e) => (e.replay ? "on" : "off")],
    ["Seed", (e) => String(e.seed)],
  ]
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead />
          {experiments.map((e, i) => (
            <TableHead key={e.id} className="text-right">
              <span className="inline-flex items-center gap-2">
                <span className="inline-block size-2.5 rounded-full" style={{ background: `var(--series-${COLORS[i]})` }} aria-hidden />
                <Link to={`/app/experiments/${e.id}`} className="hover:underline">
                  {e.name}
                </Link>
              </span>
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell className="text-muted-foreground">Status</TableCell>
          {experiments.map((e) => (
            <TableCell key={e.id} className="text-right">
              <StatusBadge status={e.status} />
            </TableCell>
          ))}
        </TableRow>
        {settings.map(([label, get]) => (
          <TableRow key={label}>
            <TableCell className="text-muted-foreground">{label}</TableCell>
            {experiments.map((e) => (
              <TableCell key={e.id} className="text-right font-mono tabular-nums">
                {get(e)}
              </TableCell>
            ))}
          </TableRow>
        ))}
        {rows.map((row) => {
          const values = experiments.map(row.get)
          const known = values.filter((v): v is number => v !== undefined)
          const best = known.length > 1 ? (row.best === "max" ? Math.max(...known) : Math.min(...known)) : undefined
          return (
            <TableRow key={row.label}>
              <TableCell className="text-muted-foreground">{row.label}</TableCell>
              {values.map((v, i) => (
                <TableCell key={experiments[i].id} className="text-right font-mono tabular-nums">
                  {v === undefined ? "—" : v === best ? <strong>{row.fmt(v)} ★</strong> : row.fmt(v)}
                  {v === best && <span className="sr-only"> (best)</span>}
                </TableCell>
              ))}
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}

function curves(experiments: Experiment[], metrics: Record<string, Metric[]>, phase: "pretrain" | "lora", value: "train" | "val"): Series[] {
  return experiments.map((e, i) => ({
    name: e.name,
    color: COLORS[i],
    points: (metrics[String(e.id)] ?? [])
      .filter((m) => m.phase === phase && (value === "train" || m.val_loss !== null))
      .map((m) => ({ x: m.step, y: value === "train" ? m.train_loss : m.val_loss! })),
  }))
}

export function ComparePage() {
  const [params] = useSearchParams()
  const ids = parseIds(params.get("ids"))
  const enough = ids.length >= 2
  const data = useApi(() => (enough ? api.compare(ids) : Promise.resolve(null)), [ids.join(",")])

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Compare"
        description="Two to four experiments side by side. ★ marks the best value in each row."
        actions={
          <Button variant="outline" asChild>
            <Link to="/app/experiments">Choose experiments</Link>
          </Button>
        }
      />
      {!enough ? (
        <EmptyState
          icon={GitCompareIcon}
          title="Pick 2 to 4 experiments"
          action={
            <Button asChild>
              <Link to="/app/experiments">Go to Experiments</Link>
            </Button>
          }
        >
          Tick the boxes next to the experiments you want, then press Compare.
        </EmptyState>
      ) : data.error ? (
        <ErrorState message={data.error} onRetry={data.reload} />
      ) : !data.data ? (
        <LoadingRows rows={6} label="Loading the comparison" />
      ) : (
        <>
          <Card>
            <CardContent>
              <ResultsTable experiments={data.data.experiments} />
            </CardContent>
          </Card>
          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Validation loss (pre-training)</CardTitle>
                <CardDescription>On text none of the models trained on. Lower is better.</CardDescription>
              </CardHeader>
              <CardContent>
                <LossChart title="Validation loss" series={curves(data.data.experiments, data.data.metrics, "pretrain", "val")} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>LoRA fine-tuning loss</CardTitle>
                <CardDescription>How fast each LoRA adapter learned the questions and answers.</CardDescription>
              </CardHeader>
              <CardContent>
                <LossChart title="LoRA fine-tuning loss" series={curves(data.data.experiments, data.data.metrics, "lora", "train")} />
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
