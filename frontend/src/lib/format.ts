/** Numbers and dates, written the same way on every page. */
const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" })
const dateOnly = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" })
const relative = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" })
const integer = new Intl.NumberFormat()

export const formatNumber = (n: number) => integer.format(n)
export const formatPercent = (n: number | null | undefined) => (n == null ? "—" : `${Math.round(n * 100)}%`)
export const formatDate = (iso: string) => dateOnly.format(new Date(iso))
export const formatDateTime = (iso: string) => dateTime.format(new Date(iso))

/** "3 minutes ago", "yesterday" */
export function formatAgo(iso: string, now = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000)
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [
    ["second", 60],
    ["minute", 60],
    ["hour", 24],
    ["day", 30],
    ["month", 12],
    ["year", Infinity],
  ]
  let value = seconds
  for (const [unit, size] of steps) {
    if (Math.abs(value) < size) return Math.abs(value) < 10 && unit === "second" ? "just now" : relative.format(value, unit)
    value = Math.round(value / size)
  }
  return dateTime.format(new Date(iso))
}

/** "12 min 5 s" between two times (or until now) */
export function formatDuration(startIso: string | null, endIso?: string | null, now = Date.now()): string {
  if (!startIso) return "—"
  const ms = (endIso ? new Date(endIso).getTime() : now) - new Date(startIso).getTime()
  const total = Math.max(0, Math.round(ms / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h) return `${h} h ${m} min`
  if (m) return `${m} min ${s} s`
  return `${s} s`
}

export const MODEL_LABELS = { base: "Base", full: "Full fine-tune", lora: "LoRA" } as const
