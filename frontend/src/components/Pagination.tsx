import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { PageMeta } from "@/types/api"

/** "21–40 of 57" with Previous / Next buttons. Hidden when everything fits on one page. */
export function Pagination({ meta, onPage }: { meta: PageMeta; onPage: (page: number) => void }) {
  if (meta.pages <= 1) return null
  const first = (meta.page - 1) * meta.per_page + 1
  const last = Math.min(meta.total, meta.page * meta.per_page)
  return (
    <nav aria-label="Pages" className="flex items-center justify-between gap-2 text-sm">
      <p className="text-muted-foreground">
        {first}–{last} of {meta.total}
      </p>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={meta.page <= 1} onClick={() => onPage(meta.page - 1)}>
          <ChevronLeftIcon /> Previous
        </Button>
        <Button variant="outline" size="sm" disabled={meta.page >= meta.pages} onClick={() => onPage(meta.page + 1)}>
          Next <ChevronRightIcon />
        </Button>
      </div>
    </nav>
  )
}
