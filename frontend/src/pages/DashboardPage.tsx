import { useCallback, useEffect, useState } from "react"
import { CircleAlertIcon, RotateCwIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/hooks/useAuth"
import { ApiError, api } from "@/services/api"
import type { Health } from "@/types/api"

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" })

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
            <dt className="text-muted-foreground">Training</dt>
            <dd>{health.training_enabled ? "Allowed on this server" : "Off on this server"}</dd>
          </dl>
        )}
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const { user } = useAuth()
  if (!user) return null
  return (
    <div className="grid gap-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Welcome, {user.name.split(" ")[0]}</h2>
        <p className="mt-1 text-muted-foreground">
          This is the start of Disciplina Studio. The Playground, Tokenizer, Experiments and the other pages in the
          sidebar are built next, one at a time.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Your account</CardTitle>
            <CardDescription>Signed in with a secure, httpOnly cookie.</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
              <dt className="text-muted-foreground">Email</dt>
              <dd className="truncate">{user.email}</dd>
              <dt className="text-muted-foreground">Role</dt>
              <dd className="capitalize">{user.role}</dd>
              <dt className="text-muted-foreground">Member since</dt>
              <dd>{dateFormat.format(new Date(user.created_at))}</dd>
            </dl>
          </CardContent>
        </Card>
        <ServerStatus />
      </div>
    </div>
  )
}
