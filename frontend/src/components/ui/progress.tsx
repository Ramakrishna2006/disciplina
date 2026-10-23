import * as React from "react"

import { cn } from "@/lib/utils"

/** A progress bar with the right ARIA roles, so screen readers announce "45 percent". */
function Progress({ className, value, label, ...props }: React.ComponentProps<"div"> & { value: number; label: string }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100)
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      data-slot="progress"
      className={cn("relative h-2 w-full overflow-hidden rounded-full bg-primary/15", className)}
      {...props}
    >
      <div className="h-full bg-primary transition-[width] duration-500" style={{ width: `${pct}%` }} />
    </div>
  )
}

export { Progress }
