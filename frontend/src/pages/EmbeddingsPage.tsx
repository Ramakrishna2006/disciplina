import { useState, type FormEvent } from "react"
import { SearchIcon } from "lucide-react"

import { ErrorState, PageHeader } from "@/components/PageState"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { NativeSelect } from "@/components/ui/native-select"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/hooks/useApi"
import { MODEL_LABELS } from "@/lib/format"
import { api } from "@/services/api"
import type { Category, EmbeddingPoint, ModelId } from "@/types/api"

// Each category gets a colour AND a shape, so the map also works without colour vision.
const CATEGORIES: Record<Category, { label: string; color: number; shape: "circle" | "square" | "triangle" }> = {
  city: { label: "City", color: 1, shape: "circle" },
  job: { label: "Job", color: 2, shape: "square" },
  food: { label: "Food", color: 3, shape: "triangle" },
}
const SIZE = 520
const PAD = 40

function Marker({ shape, x, y, color, r = 5 }: { shape: string; x: number; y: number; color: number; r?: number }) {
  const fill = `var(--series-${color})`
  if (shape === "square") return <rect x={x - r} y={y - r} width={r * 2} height={r * 2} rx={1.5} fill={fill} className="stroke-card" strokeWidth={1.5} />
  if (shape === "triangle")
    return <polygon points={`${x},${y - r - 1} ${x + r + 1},${y + r} ${x - r - 1},${y + r}`} fill={fill} className="stroke-card" strokeWidth={1.5} />
  return <circle cx={x} cy={y} r={r} fill={fill} className="stroke-card" strokeWidth={1.5} />
}

export function EmbeddingsPage() {
  const [model, setModel] = useState<ModelId>("base")
  const [selected, setSelected] = useState("Pune")
  const [search, setSearch] = useState("")
  const points = useApi(() => api.embeddings(model), [model])
  const neighbors = useApi(() => api.neighbors(selected, 5, model), [selected, model])

  function onSearch(e: FormEvent) {
    e.preventDefault()
    if (search.trim()) setSelected(search.trim())
  }

  const px = (p: EmbeddingPoint) => PAD + p.x * (SIZE - 2 * PAD)
  const py = (p: EmbeddingPoint) => PAD + (1 - p.y) * (SIZE - 2 * PAD)

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Embeddings"
        description="Every token is stored as a list of 96 numbers (its embedding). The map squeezes those 96 numbers into 2 (PCA). Nobody told the model which words are cities or foods, yet words with the same role end up close together."
        actions={
          <div className="grid gap-1.5">
            <Label htmlFor="emb-model" className="text-xs text-muted-foreground">
              Model
            </Label>
            <NativeSelect id="emb-model" value={model} onChange={(e) => setModel(e.target.value as ModelId)}>
              {(["base", "full", "lora"] as const).map((m) => (
                <option key={m} value={m}>
                  {MODEL_LABELS[m]}
                </option>
              ))}
            </NativeSelect>
          </div>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Card>
          <CardHeader>
            <CardTitle>Map of city, job and food words</CardTitle>
            <CardDescription>Select a word to see its nearest neighbours.</CardDescription>
          </CardHeader>
          <CardContent>
            {points.error ? (
              <ErrorState message={points.error} onRetry={points.reload} />
            ) : !points.data ? (
              <Skeleton className="aspect-square w-full" />
            ) : (
              <>
                <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="h-auto w-full" role="group" aria-label="Embedding map">
                  {points.data.map((p) => {
                    const cat = CATEGORIES[p.category]
                    const isSelected = p.word.toLowerCase() === selected.toLowerCase()
                    return (
                      <g
                        key={p.word}
                        role="button"
                        tabIndex={0}
                        aria-label={`${p.word} (${cat.label})`}
                        aria-pressed={isSelected}
                        className="cursor-pointer outline-none [&:focus-visible>text]:underline"
                        onClick={() => setSelected(p.word)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault()
                            setSelected(p.word)
                          }
                        }}
                      >
                        <circle cx={px(p)} cy={py(p)} r={14} fill="transparent" />
                        {isSelected && <circle cx={px(p)} cy={py(p)} r={11} fill="none" className="stroke-foreground" strokeWidth={1.5} />}
                        <Marker shape={cat.shape} x={px(p)} y={py(p)} color={cat.color} />
                        <text x={px(p) + 9} y={py(p) + 4} className={isSelected ? "fill-foreground text-[13px] font-semibold" : "fill-muted-foreground text-[12px]"}>
                          {p.word}
                        </text>
                      </g>
                    )
                  })}
                </svg>
                <div className="mt-3 flex flex-wrap gap-4 text-sm text-muted-foreground">
                  {Object.values(CATEGORIES).map((c) => (
                    <span key={c.label} className="flex items-center gap-2">
                      <svg width="14" height="14" aria-hidden>
                        <Marker shape={c.shape} x={7} y={7} color={c.color} r={4.5} />
                      </svg>
                      {c.label}
                    </span>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Nearest to “{selected}”</CardTitle>
            <CardDescription>Cosine similarity: 1 means pointing the same way, 0 unrelated.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <form onSubmit={onSearch} className="flex gap-2" role="search">
              <Label htmlFor="emb-word" className="sr-only">
                Word
              </Label>
              <Input id="emb-word" placeholder="Any word, e.g. teacher" value={search} onChange={(e) => setSearch(e.target.value)} maxLength={40} />
              <Button type="submit" variant="secondary" size="icon" aria-label="Find neighbours">
                <SearchIcon />
              </Button>
            </form>
            {neighbors.error ? (
              <p className="text-sm text-destructive" role="alert">
                {neighbors.error}
              </p>
            ) : !neighbors.data ? (
              <div className="space-y-2" aria-busy="true">
                {Array.from({ length: 5 }, (_, i) => (
                  <Skeleton key={i} className="h-6 w-full" />
                ))}
              </div>
            ) : (
              <ol className="grid gap-2" aria-busy={neighbors.loading}>
                {neighbors.data.map((n) => (
                  <li key={n.word} className="grid grid-cols-[6rem_1fr_3rem] items-center gap-2 text-sm">
                    <button type="button" className="truncate text-left font-medium hover:underline" onClick={() => setSelected(n.word)}>
                      {n.word}
                    </button>
                    <span className="h-2 rounded-full bg-primary/15">
                      <span className="block h-full rounded-full bg-primary" style={{ width: `${Math.max(0, n.similarity) * 100}%` }} />
                    </span>
                    <span className="text-right font-mono text-xs tabular-nums">{n.similarity.toFixed(2)}</span>
                  </li>
                ))}
              </ol>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
