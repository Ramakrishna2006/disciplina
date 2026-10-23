import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes, useLocation } from "react-router"
import { describe, expect, it, vi } from "vitest"

import { GuestOnlyRoute, ProtectedRoute } from "./RouteGuards"

const auth = vi.hoisted(() => ({ status: "signed-out" as "loading" | "signed-in" | "signed-out" }))
vi.mock("@/hooks/useAuth", () => ({ useAuth: () => auth }))

function ShowLocation() {
  const location = useLocation()
  return <p>At {location.pathname + location.search}</p>
}

function renderRoutes(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route path="/app/*" element={<p>Private page</p>} />
        </Route>
        <Route element={<GuestOnlyRoute />}>
          <Route path="/login" element={<ShowLocation />} />
        </Route>
      </Routes>
    </MemoryRouter>
  )
}

describe("route guards", () => {
  it("sends a signed-out visitor to sign in, remembering where they were going", () => {
    auth.status = "signed-out"
    renderRoutes("/app/experiments?tab=mine")
    expect(screen.getByText("At /login?next=%2Fapp%2Fexperiments%3Ftab%3Dmine")).toBeInTheDocument()
  })

  it("shows private pages when signed in, and skips the sign-in page", () => {
    auth.status = "signed-in"
    renderRoutes("/app/experiments")
    expect(screen.getByText("Private page")).toBeInTheDocument()
  })

  it("redirects a signed-in person away from /login", () => {
    auth.status = "signed-in"
    renderRoutes("/login")
    expect(screen.getByText("Private page")).toBeInTheDocument()
  })

  it("shows a loading placeholder while the session is being checked", () => {
    auth.status = "loading"
    renderRoutes("/app")
    expect(screen.getByLabelText("Loading")).toHaveAttribute("aria-busy", "true")
    expect(screen.queryByText("Private page")).not.toBeInTheDocument()
  })
})
