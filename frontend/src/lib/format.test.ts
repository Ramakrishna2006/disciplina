import { describe, expect, it } from "vitest"

import { formatAgo, formatDuration, formatPercent } from "./format"

describe("formatting", () => {
  it("writes scores as whole percentages, and a dash when there is none", () => {
    expect(formatPercent(0.95)).toBe("95%")
    expect(formatPercent(1)).toBe("100%")
    expect(formatPercent(null)).toBe("—")
    expect(formatPercent(undefined)).toBe("—")
  })

  it("writes durations in seconds, minutes and hours", () => {
    const start = "2026-01-01T10:00:00Z"
    expect(formatDuration(start, "2026-01-01T10:00:42Z")).toBe("42 s")
    expect(formatDuration(start, "2026-01-01T10:12:05Z")).toBe("12 min 5 s")
    expect(formatDuration(start, "2026-01-01T11:30:00Z")).toBe("1 h 30 min")
    expect(formatDuration(null)).toBe("—")
  })

  it("says 'just now' for the last few seconds and counts back further", () => {
    const now = new Date("2026-01-01T12:00:00Z").getTime()
    expect(formatAgo("2026-01-01T11:59:58Z", now)).toBe("just now")
    expect(formatAgo("2026-01-01T11:57:00Z", now)).toMatch(/3/)
  })
})
