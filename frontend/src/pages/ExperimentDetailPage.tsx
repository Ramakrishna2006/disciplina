import { useCallback, useEffect, useRef, useState } from "react"
import { Link, useNavigate, useParams } from "react-router"
import {
  ArrowLeftIcon,
  CircleAlertIcon,
  DownloadIcon,
  GlobeIcon,
  PencilIcon,
  RotateCwIcon,
  SquareIcon,
  TrashIcon,
} from "lucide-react"
import { toast } from "sonner"

import { ConfirmDialog } from "@/components/ConfirmDialog"
import { LossChart, lossSeries } from "@/components/LossChart"
import { NewExperimentDialog } from "@/components/NewExperimentDialog"
import { ErrorState, LoadingRows, PageHeader } from "@/components/PageState"
import { RenameDialog } from "@/components/RenameDialog"
import { StatusBadge } from "@/components/StatusBadge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { errorMessage, useApi, useInterval } from "@/hooks/useApi"
import { useAuth } from "@/hooks/useAuth"
import { MODEL_LABELS, formatDateTime, formatDuration, formatNumber, formatPercent } from "@/lib/format"
import { api } from "@/services/api"
import type { Experiment, Metric } from "@/types/api"

const PHASES: Record<string, string> = {
  data: "Building the tokenizer",
  pretrain: "Pre-training",
  "finetune-full": "Fine-tuning (full)",
  "finetune-lora": "Fine-tuning (LoRA)",
  evaluate: "Testing the models",
}
const POLL_MS = 2000

/** The live part: progress and loss curves, refreshed every 2 seconds while the run trains. */
function useLiveExperiment(id: number) {
  const detail = useApi(() => api.experiment(id), [id])
  const [metrics, setMetrics] = useState<Metric[]>([])
  const [metricsError, setMetricsError] = useState<string | null>(null)
  const lastId = useRef(0)
  const busy = useRef(false)

  const loadAll = useCallback(async () => {
    try {
      const page = await api.metrics(id, 0)
      lastId.current = page.meta.last_id
      setMetrics(page.items)
      setMetricsError(null)
    } catch (e) {
      setMetricsError(errorMessage(e))
    }
  }, [id])

  useEffect(() => {
    lastId.current = 0
    setMetrics([])
    void loadAll()
  }, [loadAll])

  const exp = detail.data?.experiment
  const active = exp?.status === "queued" || exp?.status === "running"

  useInterval(
    async () => {
      if (busy.current) return // the previous poll has not answered yet
      busy.current = true
      try {
        const [fresh, page] = await Promise.all([api.experiment(id), api.metrics(id, lastId.current)])
        detail.setData(fresh)
        if (page.meta.complete) {
          await loadAll() // the finished run added validation losses to earlier points
        } else if (page.items.length) {
          lastId.current = page.meta.last_id
          setMetrics((old) => [...old, ...page.items])
        }
      } catch {
        /* a missed poll is fine: the next one tries again */
      } finally {
        busy.current = false
      }
    },
    POLL_MS,
    active
  )

  return { detail, exp, metrics, metricsError, active, loadAll }
}

function TrainingLog({ id, active }: { id: number; active: boolean }) {
  const [open, setOpen] = useState(false)
  const [lines, setLines] = useState<string[] | null>(null)
  const load = useCallback(() => {
    api.runLog(id).then(setLines, () => setLines([]))
  }, [id])
  useEffect(() => {
    if (open) load()
  }, [open, load])
  useInterval(load, 3000, open && active)
  return (
    <details className="rounded-xl border bg-card p-4" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary className="cursor-pointer font-medium">Training log</summary>
      <pre className="mt-3 max-h-80 overflow-auto rounded-md bg-muted p-3 font-mono text-xs leading-relaxed">
        {lines === null ? "Loading…" : lines.length ? lines.join("\n") : "No log yet."}
      </pre>
    </details>
  )
}

function Results({ exp }: { exp: Experiment }) {
  if (!exp.results?.length) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle>Results</CardTitle>
        <CardDescription>
          “Held-out” is the real test: questions about people the model never saw a question about. Perplexity: lower is
          better (how unsure the model is about the next token).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Model</TableHead>
              <TableHead className="text-right">Trained weights</TableHead>
              <TableHead className="text-right">Q&amp;A seen</TableHead>
              <TableHead className="text-right">Q&amp;A held-out</TableHead>
              <TableHead className="text-right">Completion</TableHead>
              <TableHead className="text-right">Perplexity</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="font-mono tabular-nums">
            {exp.results.map((r) => (
              <TableRow key={r.model}>
                <TableCell className="font-sans font-medium">{MODEL_LABELS[r.model]}</TableCell>
                <TableCell className="text-right">{formatNumber(r.trainable_params)}</TableCell>
                <TableCell className="text-right">{formatPercent(r.qa_seen)}</TableCell>
                <TableCell className="text-right font-semibold">{formatPercent(r.qa_heldout)}</TableCell>
                <TableCell className="text-right">{formatPercent(r.completion)}</TableCell>
                <TableCell className="text-right">{r.perplexity.toFixed(2)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

export function ExperimentDetailPage() {
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const { user } = useAuth()
  const config = useApi(() => api.config(), [])
  const { detail, exp, metrics, metricsError, active, loadAll } = useLiveExperiment(id)

  if (detail.error) return <ErrorState message={detail.error} onRetry={detail.reload} title="Could not load this experiment" />
  if (!exp) return <LoadingRows rows={6} label="Loading the experiment" />

  const canEdit = exp.is_owner || user?.role === "admin"

  async function act(action: () => Promise<Experiment>, done: string) {
    try {
      const updated = await action()
      detail.setData((old) => ({ ...old, experiment: updated }))
      toast.success(done)
    } catch (e) {
      toast.error(errorMessage(e))
      throw e
    }
  }

  async function remove() {
    try {
      await api.deleteExperiment(exp!.id)
      toast.success("Experiment deleted.")
      navigate("/app/experiments", { replace: true })
    } catch (e) {
      toast.error(errorMessage(e))
      throw e
    }
  }

  const settings = [
    ["Pre-training steps", formatNumber(exp.pretrain_steps)],
    ["Fine-tuning steps", formatNumber(exp.finetune_steps)],
    ["LoRA rank", exp.lora_rank],
    ["Replay", exp.replay ? "on" : "off"],
    ["Seed", exp.seed],
    ["Owner", exp.is_owner ? "you" : (exp.owner_name ?? "—")],
    ["Created", formatDateTime(exp.created_at)],
    ["Training time", formatDuration(exp.started_at, exp.finished_at)],
  ] as const

  return (
    <div className="grid gap-6">
      <Link to="/app/experiments" className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" aria-hidden /> All experiments
      </Link>
      <PageHeader
        title={exp.name}
        description={exp.description || undefined}
        actions={
          <>
            {canEdit && (
              <RenameDialog
                trigger={
                  <Button variant="outline" size="sm">
                    <PencilIcon /> Rename
                  </Button>
                }
                title="Rename experiment"
                value={exp.name}
                onSave={(name) => act(() => api.updateExperiment(exp.id, { name }), "Renamed.")}
              />
            )}
            {user?.role === "admin" && exp.status === "completed" && (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  act(
                    () => api.updateExperiment(exp.id, { is_public: !exp.is_public }),
                    exp.is_public ? "No longer published." : "Published: every user can see it."
                  ).catch(() => {})
                }
              >
                <GlobeIcon /> {exp.is_public ? "Unpublish" : "Publish"}
              </Button>
            )}
            <Button variant="outline" size="sm" asChild>
              <a href={api.exportUrl(exp.id)} download>
                <DownloadIcon /> CSV
              </a>
            </Button>
            {!active && (
              <NewExperimentDialog
                config={config.data}
                initial={{
                  name: `${exp.name} (again)`.slice(0, 80),
                  description: exp.description,
                  pretrain_steps: exp.pretrain_steps,
                  finetune_steps: exp.finetune_steps,
                  lora_rank: exp.lora_rank,
                  replay: exp.replay,
                  seed: exp.seed,
                }}
                trigger={
                  <Button variant="outline" size="sm">
                    <RotateCwIcon /> Run again
                  </Button>
                }
              />
            )}
            {exp.is_owner && active && (
              <ConfirmDialog
                trigger={
                  <Button variant="outline" size="sm" disabled={exp.cancel_requested}>
                    <SquareIcon /> {exp.cancel_requested ? "Stopping…" : "Cancel"}
                  </Button>
                }
                title="Stop this experiment?"
                description="Training stops within a second. What it learned so far is not kept as a result."
                confirmLabel="Stop training"
                onConfirm={() => act(() => api.cancelExperiment(exp.id), "Stopping the experiment.")}
              />
            )}
            {canEdit && exp.status !== "running" && (
              <ConfirmDialog
                trigger={
                  <Button variant="outline" size="sm" className="text-destructive">
                    <TrashIcon /> Delete
                  </Button>
                }
                title="Delete this experiment?"
                description="Its loss curves, scores and trained model files are deleted for good."
                onConfirm={remove}
              />
            )}
          </>
        }
      />

      <Card>
        <CardContent className="grid gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge status={exp.status} />
            {exp.is_public && <span className="text-sm text-muted-foreground">Published</span>}
            {active && (
              <span className="text-sm text-muted-foreground" role="status">
                {exp.status === "queued"
                  ? `Waiting to start${detail.data?.queue_position && detail.data.queue_position > 1 ? ` (number ${detail.data.queue_position} in the queue)` : "…"}`
                  : `${PHASES[exp.phase ?? ""] ?? "Training"} · ${Math.round(exp.progress * 100)}%`}
              </span>
            )}
          </div>
          {active && <Progress value={exp.progress} label="Training progress" />}
          {exp.error && (
            <Alert variant={exp.status === "interrupted" ? "default" : "destructive"}>
              <CircleAlertIcon />
              <AlertTitle>{exp.status === "interrupted" ? "Interrupted" : "Training failed"}</AlertTitle>
              <AlertDescription>{exp.error}</AlertDescription>
            </Alert>
          )}
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
            {settings.map(([label, value]) => (
              <div key={label}>
                <dt className="text-muted-foreground">{label}</dt>
                <dd className="font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      {metricsError && <ErrorState message={metricsError} onRetry={loadAll} title="Could not load the loss curves" />}
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Pre-training loss</CardTitle>
            <CardDescription>Learning to predict the next token. Validation (dashed) is text the model never trains on.</CardDescription>
          </CardHeader>
          <CardContent>
            <LossChart title="Pre-training loss" series={lossSeries(metrics, "pretrain")} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Fine-tuning loss</CardTitle>
            <CardDescription>Learning to answer questions: all weights (full) versus small LoRA adapters.</CardDescription>
          </CardHeader>
          <CardContent>
            <LossChart title="Fine-tuning loss" series={lossSeries(metrics, "finetune")} />
          </CardContent>
        </Card>
      </div>

      <Results exp={exp} />
      <TrainingLog id={exp.id} active={active} />
    </div>
  )
}
