import { useState } from "react"
import { Link } from "react-router"
import { ActivityIcon, CheckCheckIcon } from "lucide-react"
import { toast } from "sonner"

import { activityIcon } from "@/components/NotificationBell"
import { Pagination } from "@/components/Pagination"
import { EmptyState, ErrorState, LoadingRows, PageHeader } from "@/components/PageState"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { errorMessage, useApi } from "@/hooks/useApi"
import { formatAgo, formatDateTime } from "@/lib/format"
import { cn } from "@/lib/utils"
import { api } from "@/services/api"

export function ActivityPage() {
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [page, setPage] = useState(1)
  const list = useApi(() => api.activity({ unread: unreadOnly || null, page, per_page: 20 }), [unreadOnly, page])
  const unread = list.data?.meta.unread ?? 0

  async function markAll() {
    try {
      await api.markRead()
      window.dispatchEvent(new Event("activity-read")) // tells the bell to update
      list.reload()
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Activity"
        description="What happened to your experiments: finished, failed, cancelled or interrupted."
        actions={
          <>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={unreadOnly}
                onChange={(e) => {
                  setUnreadOnly(e.target.checked)
                  setPage(1)
                }}
              />
              Unread only
            </label>
            <Button variant="outline" onClick={markAll} disabled={unread === 0}>
              <CheckCheckIcon /> Mark all as read
            </Button>
          </>
        }
      />
      {list.error ? (
        <ErrorState message={list.error} onRetry={list.reload} />
      ) : !list.data ? (
        <LoadingRows rows={5} label="Loading activity" />
      ) : list.data.items.length === 0 ? (
        <EmptyState icon={ActivityIcon} title={unreadOnly ? "All caught up" : "No activity yet"}>
          {unreadOnly ? "You have read everything." : "When an experiment finishes, it shows up here."}
        </EmptyState>
      ) : (
        <Card className="py-2">
          <CardContent className="px-2">
            <ul className="divide-y">
              {list.data.items.map((e) => {
                const Icon = activityIcon(e.type)
                return (
                  <li key={e.id} className={cn("flex items-start gap-3 px-3 py-3", !e.read_at && "bg-accent/40")}>
                    <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm">
                        {!e.read_at && <span className="sr-only">Unread: </span>}
                        {e.experiment_id ? (
                          <Link to={`/app/experiments/${e.experiment_id}`} className="hover:underline">
                            {e.message}
                          </Link>
                        ) : (
                          e.message
                        )}
                      </p>
                      <time dateTime={e.created_at} title={formatDateTime(e.created_at)} className="text-xs text-muted-foreground">
                        {formatAgo(e.created_at)}
                      </time>
                    </div>
                    {!e.read_at && <span className="mt-1.5 size-2 shrink-0 rounded-full bg-primary" aria-hidden />}
                  </li>
                )
              })}
            </ul>
          </CardContent>
        </Card>
      )}
      {list.data && <Pagination meta={list.data.meta} onPage={setPage} />}
    </div>
  )
}
