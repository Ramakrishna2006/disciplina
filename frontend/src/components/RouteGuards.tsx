import { Navigate, Outlet, useLocation } from "react-router"

import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/hooks/useAuth"

function FullPageLoading() {
  return (
    <div className="flex min-h-svh items-center justify-center" aria-busy="true" aria-label="Loading">
      <div className="w-72 space-y-3">
        <Skeleton className="h-6 w-1/2" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
      </div>
    </div>
  )
}

/** Pages for signed-in people. Others go to /login and come back here afterwards (?next=). */
export function ProtectedRoute() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === "loading") return <FullPageLoading />
  if (status === "signed-out") {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  return <Outlet />
}

/** Sign-in and sign-up: someone already signed in goes straight to the app. */
export function GuestOnlyRoute() {
  const { status } = useAuth()
  if (status === "loading") return <FullPageLoading />
  if (status === "signed-in") return <Navigate to="/app" replace />
  return <Outlet />
}

/** Only follow ?next= to pages on this site ("/app/..."), never to another website. */
export function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return "/app"
  return value
}
