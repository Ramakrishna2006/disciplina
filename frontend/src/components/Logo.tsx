import { Link } from "react-router"

import { cn } from "@/lib/utils"

/** The Disciplina "D" mark (public/favicon.svg) with the product name. */
export function Logo({ to = "/", className }: { to?: string; className?: string }) {
  return (
    <Link to={to} className={cn("flex items-center gap-2.5 rounded-md font-semibold tracking-tight", className)}>
      <img src="/favicon.svg" alt="" width={28} height={28} className="size-7" />
      <span>
        Disciplina <span className="font-normal text-muted-foreground">Studio</span>
      </span>
    </Link>
  )
}
