import { useCallback, useEffect, useRef, useState, type DependencyList } from "react"

import { ApiError } from "@/services/api"

export interface ApiState<T> {
  data: T | undefined
  error: string | null
  loading: boolean
  /** Load again (the "Try again" button, or after a change). */
  reload: () => void
  /** Change the loaded data in place, e.g. after a successful edit, without asking the server. */
  setData: (update: T | ((old: T | undefined) => T)) => void
}

export function errorMessage(e: unknown, fallback = "Something went wrong. Please try again."): string {
  return e instanceof ApiError ? e.message : fallback
}

/**
 * Load data for a page: `const { data, error, loading, reload } = useApi(() => api.facets(), [])`.
 * Gives every page the same three states (loading, error with "Try again", ready). When `deps`
 * change, the old request is ignored, so a slow answer can never overwrite a newer one.
 */
export function useApi<T>(load: () => Promise<T>, deps: DependencyList): ApiState<T> {
  const [data, setDataState] = useState<T | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)
  const loadRef = useRef(load)
  loadRef.current = load

  useEffect(() => {
    let current = true
    setLoading(true)
    setError(null)
    loadRef
      .current()
      .then((result) => {
        if (current) setDataState(result)
      })
      .catch((e: unknown) => {
        if (current) setError(errorMessage(e, "Could not load this. Check your connection and try again."))
      })
      .finally(() => {
        if (current) setLoading(false)
      })
    return () => {
      current = false
    }
    // The caller lists what the request depends on (like useEffect); `attempt` changes on reload().
  }, [...deps, attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  const setData = useCallback((update: T | ((old: T | undefined) => T)) => {
    setDataState((old) => (typeof update === "function" ? (update as (o: T | undefined) => T)(old) : update))
  }, [])
  return { data, error, loading, reload, setData }
}

/** Call `tick` every `ms` milliseconds while `active` is true, and pause while the tab is hidden. */
export function useInterval(tick: () => void, ms: number, active = true) {
  const tickRef = useRef(tick)
  tickRef.current = tick
  useEffect(() => {
    if (!active) return
    const id = window.setInterval(() => {
      if (document.visibilityState !== "hidden") tickRef.current()
    }, ms)
    return () => window.clearInterval(id)
  }, [ms, active])
}

/** `value`, but only after it stopped changing for `ms` milliseconds (for type-as-you-go search). */
export function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), ms)
    return () => window.clearTimeout(id)
  }, [value, ms])
  return debounced
}
