import { useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router"
import { FlaskConicalIcon, GitCompareIcon, PlusIcon } from "lucide-react"

import { NewExperimentDialog } from "@/components/NewExperimentDialog"
import { Pagination } from "@/components/Pagination"
import { EmptyState, ErrorState, LoadingRows, PageHeader } from "@/components/PageState"
import { StatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { NativeSelect } from "@/components/ui/native-select"
import { Progress } from "@/components/ui/progress"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useApi, useDebounced, useInterval } from "@/hooks/useApi"
import { formatAgo, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"
import { api } from "@/services/api"
import type { Experiment } from "@/types/api"

const STATUSES = ["queued", "running", "completed", "failed", "cancelled", "interrupted"] as const
const SORTS = [
  { value: "created_at:desc", label: "Newest first" },
  { value: "created_at:asc", label: "Oldest first" },
  { value: "name:asc", label: "Name A–Z" },
  { value: "qa_heldout:desc", label: "Best held-out score" },
]

function lora(e: Experiment) {
  return e.results?.find((r) => r.model === "lora")
}

export function ExperimentsPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const scope = params.get("scope") === "public" ? "public" : "mine"
  const status = params.get("status") ?? ""
  const sortValue = params.get("sort") ?? "created_at:desc"
  const [sort, order] = sortValue.split(":")
  const page = Number(params.get("page")) || 1
  const [search, setSearch] = useState("")
  const debounced = useDebounced(search, 300)
  const [selected, setSelected] = useState<number[]>([])

  const config = useApi(() => api.config(), [])
  const list = useApi(
    () => api.experiments({ scope, status, sort, order, page, search: debounced, per_page: 20 }),
    [scope, status, sort, order, page, debounced]
  )
  const hasActive = list.data?.items.some((e) => e.status === "queued" || e.status === "running") ?? false
  // While something trains, refresh the list every 3 seconds so progress moves.
  useInterval(list.reload, 3000, hasActive)

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params)
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v)
      else next.delete(k)
    }
    if (!("page" in changes)) next.delete("page")
    setParams(next)
  }

  function toggle(id: number) {
    setSelected((old) => (old.includes(id) ? old.filter((x) => x !== id) : old.length >= 4 ? old : [...old, id]))
  }

  const newButton = (
    <NewExperimentDialog
      config={config.data}
      trigger={
        <Button>
          <PlusIcon /> New experiment
        </Button>
      }
    />
  )

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Experiments"
        description="Each experiment trains the whole recipe with your settings, then tests the three models it made. Change one setting at a time and compare."
        actions={
          <>
            <Button variant="outline" disabled={selected.length < 2} onClick={() => navigate(`/app/compare?ids=${selected.join(",")}`)}>
              <GitCompareIcon /> Compare{selected.length ? ` (${selected.length})` : ""}
            </Button>
            {newButton}
          </>
        }
      />

      <div className="flex flex-wrap items-end gap-3">
        <div role="tablist" aria-label="Whose experiments" className="inline-flex rounded-md border p-0.5">
          {(["mine", "public"] as const).map((s) => (
            <button
              key={s}
              role="tab"
              aria-selected={scope === s}
              onClick={() => update({ scope: s === "mine" ? null : s })}
              className={cn(
                "rounded-sm px-3 py-1.5 text-sm font-medium outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                scope === s ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {s === "mine" ? "Mine" : "Published"}
            </button>
          ))}
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="ex-search" className="text-xs text-muted-foreground">
            Search
          </Label>
          <Input id="ex-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name or description" className="w-56" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="ex-status" className="text-xs text-muted-foreground">
            Status
          </Label>
          <NativeSelect id="ex-status" value={status} onChange={(e) => update({ status: e.target.value || null })}>
            <option value="">Any</option>
            {STATUSES.map((s) => (
              <option key={s} value={s} className="capitalize">
                {s}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="ex-sort" className="text-xs text-muted-foreground">
            Sort
          </Label>
          <NativeSelect id="ex-sort" value={sortValue} onChange={(e) => update({ sort: e.target.value })}>
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      {list.error ? (
        <ErrorState message={list.error} onRetry={list.reload} />
      ) : !list.data ? (
        <LoadingRows rows={5} label="Loading experiments" />
      ) : list.data.items.length === 0 ? (
        <EmptyState
          icon={FlaskConicalIcon}
          title={scope === "public" ? "Nothing published yet" : status || debounced ? "No experiments match" : "No experiments yet"}
          action={scope === "mine" && !status && !debounced ? newButton : undefined}
        >
          {scope === "mine" && !status && !debounced
            ? "Start with the quick preset: it trains in about 5 minutes on a laptop."
            : "Try other filters."}
        </EmptyState>
      ) : (
        <Card className="py-2">
          <CardContent className="px-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8">
                    <span className="sr-only">Select to compare</span>
                  </TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Steps</TableHead>
                  <TableHead className="text-right">Rank</TableHead>
                  <TableHead>Replay</TableHead>
                  <TableHead className="text-right">LoRA held-out</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.data.items.map((e) => (
                  <TableRow key={e.id} data-state={selected.includes(e.id) ? "selected" : undefined}>
                    <TableCell>
                      <input
                        type="checkbox"
                        className="size-4 accent-primary"
                        aria-label={`Select ${e.name} to compare`}
                        checked={selected.includes(e.id)}
                        disabled={!selected.includes(e.id) && selected.length >= 4}
                        onChange={() => toggle(e.id)}
                      />
                    </TableCell>
                    <TableCell className="max-w-64">
                      <Link to={`/app/experiments/${e.id}`} className="block truncate font-medium hover:underline">
                        {e.name}
                      </Link>
                      {scope === "public" && e.owner_name && <span className="text-xs text-muted-foreground">by {e.owner_name}</span>}
                    </TableCell>
                    <TableCell>
                      <div className="grid gap-1">
                        <StatusBadge status={e.status} />
                        {e.status === "running" && <Progress value={e.progress} label={`${e.name} progress`} className="h-1 w-24" />}
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {e.pretrain_steps}+{e.finetune_steps}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">{e.lora_rank}</TableCell>
                    <TableCell>{e.replay ? "on" : "off"}</TableCell>
                    <TableCell className="text-right font-mono tabular-nums">{formatPercent(lora(e)?.qa_heldout)}</TableCell>
                    <TableCell className="text-muted-foreground">{formatAgo(e.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      {list.data && <Pagination meta={list.data.meta} onPage={(p) => update({ page: String(p) })} />}
      {selected.length > 0 && (
        <p className="text-sm text-muted-foreground" role="status">
          {selected.length} selected for comparing (2 to 4).{" "}
          <button type="button" className="text-primary hover:underline" onClick={() => setSelected([])}>
            Clear
          </button>
        </p>
      )}
    </div>
  )
}
