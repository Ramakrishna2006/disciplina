import type { ReactElement } from "react"
import { render } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"

/** Render a page inside a router at `url`, with a marker page at `/app` and `/app/*` to land on. */
export function renderAt(url: string, path: string, page: ReactElement) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path={path} element={page} />
        <Route path="/app/*" element={<p>Landed in the app</p>} />
        <Route path="/login" element={<p>Sign-in page</p>} />
      </Routes>
    </MemoryRouter>
  )
}
