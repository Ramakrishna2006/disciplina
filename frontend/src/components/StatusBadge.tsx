import { LoaderCircleIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { ExperimentStatus } from "@/types/api"

const STYLES: Record<ExperimentStatus, { label: string; variant: "default" | "secondary" | "destructive" | "success" | "warning" | "outline" }> = {
  queued: { label: "Queued", variant: "secondary" },
  running: { label: "Training", variant: "default" },
  completed: { label: "Completed", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
  cancelled: { label: "Cancelled", variant: "outline" },
  interrupted: { label: "Interrupted", variant: "warning" },
}

export function StatusBadge({ status }: { status: ExperimentStatus }) {
  const { label, variant } = STYLES[status]
  return (
    <Badge variant={variant}>
      {status === "running" && <LoaderCircleIcon className="animate-spin" aria-hidden />}
      {label}
    </Badge>
  )
}
