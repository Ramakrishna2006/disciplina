import { Link } from "react-router"

import { Button } from "@/components/ui/button"

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60svh] flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="font-mono text-sm text-muted-foreground">404</p>
      <h1 className="text-2xl font-semibold tracking-tight">This page does not exist</h1>
      <p className="max-w-md text-muted-foreground">The address may be mistyped, or the page has moved.</p>
      <Button asChild>
        <Link to="/">Go to the home page</Link>
      </Button>
    </div>
  )
}
