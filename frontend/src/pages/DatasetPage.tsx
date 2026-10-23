import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router"
import { ArrowDownIcon, ArrowUpIcon, DatabaseIcon, MessageSquareIcon } from "lucide-react"

import { Pagination } from "@/components/Pagination"
import { EmptyState, ErrorState, LoadingRows, PageHeader } from "@/components/PageState"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { NativeSelect } from "@/components/ui/native-select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useApi, useDebounced } from "@/hooks/useApi"
import { api } from "@/services/api"

const COLUMNS = [
  { key: "name", label: "Name" },
  { key: "city", label: "City" },
  { key: "job", label: "Job" },
  { key: "food", label: "Favourite food" },
  { key: "split", label: "Used for" },
] as const
const FILTERS = ["city", "job", "food", "split"] as const

export function DatasetPage() {
  // The filters live in the address bar, so a filtered view can be bookmarked or shared.
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState(params.get("search") ?? "")
  const debounced = useDebounced(search, 300)
  const sort = params.get("sort") ?? "name"
  const order = params.get("order") === "desc" ? "desc" : "asc"
  const page = Number(params.get("page")) || 1

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params)
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v)
      else next.delete(k)
    }
    if (!("page" in changes)) next.delete("page") // a new filter starts at page 1
    setParams(next)
  }

  useEffect(() => {
    // Only the (debounced) search text triggers this; the other filters update the address directly.
    if (debounced !== (params.get("search") ?? "")) update({ search: debounced || null })
  }, [debounced])

  const facets = useApi(() => api.facets(), [])
  const query = params.toString()
  const people = useApi(
    () =>
      api.people({
        search: params.get("search"),
        city: params.get("city"),
        job: params.get("job"),
        food: params.get("food"),
        split: params.get("split"),
        sort,
        order,
        page,
        per_page: 20,
      }),
    [query]
  )

  function sortBy(key: string) {
    update({ sort: key, order: sort === key && order === "asc" ? "desc" : "asc" })
  }

  const filtered = FILTERS.some((f) => params.get(f)) || !!params.get("search")

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Dataset"
        description="The 40 made-up people every model learned about. Each has a city, a job and a favourite food. The models saw questions and answers about the fine-tuning people only; held-out people appear only in plain text, so questions about them test real understanding."
      />

      <Card className="py-4">
        <CardContent className="grid gap-3 px-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="grid gap-1.5">
            <Label htmlFor="ds-search">Search</Label>
            <Input id="ds-search" type="search" placeholder="Name, city, job…" value={search} onChange={(e) => setSearch(e.target.value)} maxLength={40} />
          </div>
          {FILTERS.map((f) => (
            <div key={f} className="grid gap-1.5">
              <Label htmlFor={`ds-${f}`} className="capitalize">
                {f === "split" ? "Used for" : f}
              </Label>
              <NativeSelect id={`ds-${f}`} value={params.get(f) ?? ""} onChange={(e) => update({ [f]: e.target.value || null })}>
                <option value="">All</option>
                {facets.data?.[f].map((v) => (
                  <option key={v.value} value={v.value}>
                    {v.value} ({v.count})
                  </option>
                ))}
              </NativeSelect>
            </div>
          ))}
        </CardContent>
      </Card>

      {people.error ? (
        <ErrorState message={people.error} onRetry={people.reload} />
      ) : !people.data ? (
        <LoadingRows rows={8} label="Loading people" />
      ) : people.data.items.length === 0 ? (
        <EmptyState
          icon={DatabaseIcon}
          title={filtered ? "Nobody matches" : "The dataset is empty"}
          action={
            filtered ? (
              <Button
                variant="outline"
                onClick={() => {
                  setSearch("")
                  setParams(new URLSearchParams())
                }}
              >
                Clear filters
              </Button>
            ) : undefined
          }
        >
          {filtered ? "Try another search or filter." : "Run `flask --app backend.app seed` to add the 40 people."}
        </EmptyState>
      ) : (
        <Card className="py-2" aria-busy={people.loading}>
          <CardContent className="px-2">
            <Table>
              <TableHeader>
                <TableRow>
                  {COLUMNS.map((c) => (
                    <TableHead key={c.key} aria-sort={sort === c.key ? (order === "asc" ? "ascending" : "descending") : "none"}>
                      <button type="button" className="inline-flex items-center gap-1 hover:underline" onClick={() => sortBy(c.key)}>
                        {c.label}
                        {sort === c.key && (order === "asc" ? <ArrowUpIcon className="size-3.5" aria-hidden /> : <ArrowDownIcon className="size-3.5" aria-hidden />)}
                      </button>
                    </TableHead>
                  ))}
                  <TableHead>
                    <span className="sr-only">Ask</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {people.data.items.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{p.name}</TableCell>
                    <TableCell>{p.city}</TableCell>
                    <TableCell>{p.job}</TableCell>
                    <TableCell>{p.food}</TableCell>
                    <TableCell>
                      <Badge variant={p.split === "held-out" ? "warning" : "secondary"}>{p.split}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button asChild variant="ghost" size="sm">
                        <Link to={`/app/playground?ask=${encodeURIComponent(`Where does ${p.name} live?`)}`} aria-label={`Ask about ${p.name}`}>
                          <MessageSquareIcon /> Ask
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      {people.data && <Pagination meta={people.data.meta} onPage={(p) => update({ page: String(p) })} />}
    </div>
  )
}
