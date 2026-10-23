import { beforeEach, describe, expect, it, vi } from "vitest"

import { ApiError, api, request } from "./api"

function json(status: number, body: unknown) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

const USER = { id: 1, email: "asha@example.com", name: "Asha" }
let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal("fetch", fetchMock)
})

function headersOf(call: number): Record<string, string> {
  return fetchMock.mock.calls[call][1].headers
}

describe("CSRF protection", () => {
  it("copies csrf_access_token into X-CSRF-TOKEN on change requests only", async () => {
    document.cookie = "csrf_access_token=abc123; path=/"
    fetchMock.mockResolvedValueOnce(json(200, { data: { user: USER } }))
    fetchMock.mockResolvedValueOnce(json(200, { data: { user: USER } }))
    await request("PATCH", "/api/users/me", { theme: "dark" })
    await api.me()
    expect(headersOf(0)["X-CSRF-TOKEN"]).toBe("abc123")
    expect(headersOf(1)["X-CSRF-TOKEN"]).toBeUndefined()
    expect(fetchMock.mock.calls[0][1].credentials).toBe("same-origin")
  })

  it("never puts a token in JavaScript-visible storage", async () => {
    fetchMock.mockResolvedValueOnce(json(200, { data: { user: USER } }))
    await api.login("asha@example.com", "correct horse")
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })
})

describe("refresh and retry", () => {
  it("refreshes an expired session once and repeats the request", async () => {
    document.cookie = "csrf_refresh_token=r1; path=/"
    fetchMock
      .mockResolvedValueOnce(json(401, { error: { code: "token_expired", message: "expired", fields: {} } }))
      .mockResolvedValueOnce(json(200, { data: { user: USER } })) // POST /api/auth/refresh
      .mockResolvedValueOnce(json(200, { data: { user: USER } })) // the repeated request
    await expect(api.me()).resolves.toEqual(USER)
    expect(fetchMock.mock.calls.map((c: unknown[]) => c[0])).toEqual(["/api/auth/me", "/api/auth/refresh", "/api/auth/me"])
    expect(headersOf(1)["X-CSRF-TOKEN"]).toBe("r1") // refresh uses the refresh token's CSRF value
  })

  it("gives up if the refresh fails", async () => {
    document.cookie = "csrf_refresh_token=r1; path=/"
    fetchMock
      .mockResolvedValueOnce(json(401, { error: { code: "token_expired", message: "expired", fields: {} } }))
      .mockResolvedValueOnce(json(401, { error: { code: "token_revoked", message: "signed out", fields: {} } }))
    await expect(api.me()).rejects.toMatchObject({ status: 401, code: "token_expired" })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("does not try to refresh when there is no refresh cookie, or for login", async () => {
    fetchMock.mockResolvedValue(json(401, { error: { code: "not_signed_in", message: "Please sign in.", fields: {} } }))
    await expect(api.me()).rejects.toMatchObject({ code: "not_signed_in" })
    document.cookie = "csrf_refresh_token=r1; path=/"
    await expect(api.login("a@b.co", "wrong")).rejects.toMatchObject({ status: 401 })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("shares one refresh between requests that expire together", async () => {
    document.cookie = "csrf_refresh_token=r1; path=/"
    const expired = () => json(401, { error: { code: "token_expired", message: "expired", fields: {} } })
    fetchMock.mockImplementation(async (path: string) =>
      path === "/api/auth/refresh" ? json(200, { data: { user: USER } }) : expired()
    )
    await Promise.allSettled([api.me(), api.me()])
    expect(fetchMock.mock.calls.filter((c: unknown[]) => c[0] === "/api/auth/refresh")).toHaveLength(1)
  })
})

describe("errors", () => {
  it("turns an error body into an ApiError with code, fields and request id", async () => {
    fetchMock.mockResolvedValueOnce(
      json(409, { error: { code: "email_taken", message: "Taken.", fields: { email: "Registered." }, request_id: "abc" } })
    )
    const error = await api.register("A", "a@b.co", "correct horse").catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 409, code: "email_taken", fields: { email: "Registered." }, requestId: "abc" })
  })

  it("explains a network failure in plain words", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"))
    await expect(api.health()).rejects.toMatchObject({ status: 0, code: "network_error" })
  })

  it("handles a server error that is not JSON", async () => {
    fetchMock.mockResolvedValueOnce(new Response("<html>Bad gateway</html>", { status: 502 }))
    await expect(api.health()).rejects.toMatchObject({ status: 502, code: "server_error" })
  })

  it("returns nothing for 204 No Content", async () => {
    fetchMock.mockResolvedValueOnce(json(204, null))
    await expect(request("DELETE", "/api/users/me", { password: "x" })).resolves.toBeUndefined()
  })
})

describe("lists and query strings", () => {
  it("leaves empty values out of the query string", async () => {
    const { query } = await import("./api")
    expect(query({ page: 2, search: "", city: null, split: undefined, replay: false })).toBe("?page=2&replay=false")
    expect(query({})).toBe("")
  })

  it("returns the items and the page numbers of a paged list", async () => {
    const meta = { page: 1, per_page: 20, total: 1, pages: 1 }
    fetchMock.mockResolvedValueOnce(json(200, { data: [{ id: 3, name: "Leela" }], meta }))
    const result = await api.people({ search: "lee" })
    expect(fetchMock.mock.calls[0][0]).toBe("/api/people?search=lee")
    expect(result).toEqual({ items: [{ id: 3, name: "Leela" }], meta })
  })

  it("treats 204 No Content as success", async () => {
    document.cookie = "csrf_access_token=abc123; path=/"
    fetchMock.mockResolvedValueOnce(json(204, null))
    await expect(api.deleteExperiment(7)).resolves.toBeUndefined()
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE")
  })
})
