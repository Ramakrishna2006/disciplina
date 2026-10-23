import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router"
import { CircleAlertIcon, FlaskConicalIcon, MessageSquareIcon, RotateCwIcon } from "lucide-react"

import { LossChart, lossSeries } from "@/components/LossChart"
import { EmptyState, ErrorState, LoadingRows, PageHeader } from "@/components/PageState"
import { StatusBadge } from "@/components/StatusBadge"
import { Progress } from "@/components/ui/progress"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi, useInterval } from "@/hooks/useApi"
import { useAuth } from "@/hooks/useAuth"
import { formatAgo, formatNumber, formatPercent } from "@/lib/format"
import { ApiError, api } from "@/services/api"
import type { Health } from "@/types/api"

/** Shows the three screen states from the plan: loading (skeleton), error (Try again), ready. */
function ServerStatus() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setHealth(null)
    setError(null)
    api
      .health()
      .then(setHealth)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load the server status."))
  }, [])

  useEffect(load, [load])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Server</CardTitle>
        <CardDescription>The Flask API and its database.</CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <Alert variant="destructive">
            <CircleAlertIcon />
            <AlertTitle>Server not reachable</AlertTitle>
            <AlertDescription>
              <p>{error}</p>
              <Button variant="outline" size="sm" className="mt-2" onClick={load}>
                <RotateCwIcon /> Try again
              </Button>
            </AlertDescription>
          </Alert>
        ) : !health ? (
          <div className="space-y-2" aria-busy="true" aria-label="Loading server status">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-3/5" />
          </div>
        ) : (
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
            <dt className="text-muted-foreground">Status</dt>
            <dd className={health.status === "ok" ? "text-success" : "text-warning"}>
              {health.status === "ok" ? "Running" : "Degraded"}
            </dd>
            <dt className="text-muted-foreground">Database</dt>
            <dd>{health.database === "ok" ? "Connected" : "Unreachable"}</dd>
            <dt className="text-muted-foreground">Version</dt>
            <dd className="font-mono">{health.version}</dd>
            <dt className="text-muted-foreground">Models</dt>
            <dd>{health.models === "missing" ? "Missing (run python main.py train)" : "Ready"}</dd>
            <dt className="text-muted-foreground">Training</dt>
            <dd>{health.training_enabled ? "Allowed on this server" : "Off on this server"}</dd>
          </dl>
        )}
      </CardContent>
    </Card>
  )
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="gap-1 py-4">
      <CardContent className="px-4">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
        {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const { user } = useAuth()
  const dash = useApi(() => api.dashboard(), [])
  const active = dash.data?.active_experiment
  useInterval(dash.reload, 5000, !!active) // keep the progress bar moving
  if (!user) return null
  const k = dash.data?.kpis

  return (
    <div className="grid gap-6">
      <PageHeader
        title={`Welcome, ${user.name.split(" ")[0]}`}
        description="A GPT-style language model trained from scratch in NumPy. Talk to it, look inside it, and train your own versions."
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/app/playground">
                <MessageSquareIcon /> Playground
              </Link>
            </Button>
            <Button asChild>
              <Link to="/app/experiments">
                <FlaskConicalIcon /> Experiments
              </Link>
            </Button>
          </>
        }
      />

      {dash.error ? (
        <ErrorState message={dash.error} onRetry={dash.reload} />
      ) : !k ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4" aria-busy="true" aria-label="Loading your numbers">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Kpi label="Experiments" value={formatNumber(k.experiments)} hint={`${k.completed} completed`} />
          <Kpi label="Training now" value={formatNumber(k.active)} hint={k.active ? "see below" : "nothing running"} />
          <Kpi label="Conversations" value={formatNumber(k.chats)} hint={`${k.questions} questions asked`} />
          <Kpi label="Best held-out score" value={formatPercent(k.best_heldout)} hint="questions about unseen people" />
        </div>
      )}

      {active && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-3">
              <Link to={`/app/experiments/${active.id}`} className="hover:underline">
                {active.name}
              </Link>
              <StatusBadge status={active.status} />
            </CardTitle>
            <CardDescription>{Math.round(active.progress * 100)}% done</CardDescription>
          </CardHeader>
          <CardContent>
            <Progress value={active.progress} label={`${active.name} progress`} />
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Latest loss curve</CardTitle>
            <CardDescription>
              {dash.data?.latest ? (
                <>
                  Pre-training of{" "}
                  <Link to={`/app/experiments/${dash.data.latest.experiment.id}`} className="text-primary hover:underline">
                    {dash.data.latest.experiment.name}
                  </Link>
                </>
              ) : (
                "Finish an experiment to see its curve here."
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!dash.data ? (
              <Skeleton className="h-56 w-full" />
            ) : dash.data.latest ? (
              <LossChart title="Pre-training loss" series={lossSeries(dash.data.latest.metrics, "pretrain")} />
            ) : (
              <EmptyState icon={FlaskConicalIcon} title="No finished experiments">
                Run <code>flask --app backend.app seed</code> to add the published reference run.
              </EmptyState>
            )}
          </CardContent>
        </Card>

        <div className="grid content-start gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Recent activity</CardTitle>
            </CardHeader>
            <CardContent>
              {!dash.data ? (
                <LoadingRows rows={3} />
              ) : dash.data.activity.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nothing yet. Finished experiments show up here.</p>
              ) : (
                <ul className="grid gap-3">
                  {dash.data.activity.map((e) => (
                    <li key={e.id} className="text-sm">
                      {e.experiment_id ? (
                        <Link to={`/app/experiments/${e.experiment_id}`} className="hover:underline">
                          {e.message}
                        </Link>
                      ) : (
                        e.message
                      )}
                      <span className="block text-xs text-muted-foreground">{formatAgo(e.created_at)}</span>
                    </li>
                  ))}
                </ul>
              )}
              <Link to="/app/activity" className="mt-4 inline-block text-sm text-primary hover:underline">
                All activity
              </Link>
            </CardContent>
          </Card>
          <ServerStatus />
        </div>
      </div>
    </div>
  )
}
