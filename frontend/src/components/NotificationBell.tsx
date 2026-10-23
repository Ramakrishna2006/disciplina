import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate } from "react-router"
import { BellIcon, CircleAlertIcon, CircleCheckIcon, CircleSlashIcon, CirclePauseIcon, type LucideIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useInterval } from "@/hooks/useApi"
import { formatAgo } from "@/lib/format"
import { api } from "@/services/api"
import type { ActivityEvent } from "@/types/api"

export function activityIcon(type: string): LucideIcon {
  if (type.endsWith("completed")) return CircleCheckIcon
  if (type.endsWith("failed")) return CircleAlertIcon
  if (type.endsWith("cancelled")) return CircleSlashIcon
  return CirclePauseIcon
}

/** The bell in the header: the number of unread events, and the latest five. Checks every 30 s. */
export function NotificationBell() {
  const navigate = useNavigate()
  const [events, setEvents] = useState<ActivityEvent[]>([])
  const [unread, setUnread] = useState(0)

  const load = useCallback(() => {
    api.activity({ per_page: 5 }).then(
      ({ items, meta }) => {
        setEvents(items)
        setUnread(meta.unread)
      },
      () => {} // the bell stays quiet if the server is unreachable; pages show their own errors
    )
  }, [])

  useEffect(() => {
    load()
    window.addEventListener("activity-read", load)
    return () => window.removeEventListener("activity-read", load)
  }, [load])
  useInterval(load, 30_000)

  async function onOpen(open: boolean) {
    if (open && unread > 0) {
      try {
        const r = await api.markRead(events.filter((e) => !e.read_at).map((e) => e.id))
        setUnread(r.unread)
      } catch {
        /* not marked; it is tried again next time */
      }
    }
  }

  return (
    <DropdownMenu onOpenChange={onOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}>
          <BellIcon />
          {unread > 0 && (
            <span className="absolute top-1 right-1 flex min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] leading-4 font-semibold text-primary-foreground">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>Activity</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {events.length === 0 ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">Nothing yet. Finished experiments show up here.</p>
        ) : (
          events.map((e) => {
            const Icon = activityIcon(e.type)
            return (
              <DropdownMenuItem
                key={e.id}
                className="items-start"
                onSelect={() => e.experiment_id && navigate(`/app/experiments/${e.experiment_id}`)}
              >
                <Icon className="mt-0.5" />
                <span className="grid gap-0.5">
                  <span className={e.read_at ? "" : "font-medium"}>{e.message}</span>
                  <span className="text-xs text-muted-foreground">{formatAgo(e.created_at)}</span>
                </span>
              </DropdownMenuItem>
            )
          })
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/app/activity">See all activity</Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
