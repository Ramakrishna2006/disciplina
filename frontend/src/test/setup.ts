// Runs before every test file: adds DOM matchers (toBeInTheDocument, toHaveAttribute ...) and
// cleans up rendered components and mocks after each test.
import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach, vi } from "vitest"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  document.cookie.split(";").forEach((c) => {
    const name = c.split("=")[0].trim()
    if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
  })
})

// jsdom has no matchMedia; the theme code asks it whether the system is in dark mode.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}
