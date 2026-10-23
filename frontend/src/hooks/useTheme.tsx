import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"

export type Theme = "system" | "light" | "dark"
type Resolved = "light" | "dark"

const STORAGE_KEY = "disciplina-theme" // the same key public/theme-init.js reads

interface ThemeContextValue {
  theme: Theme // what the user chose
  resolvedTheme: Resolved // what is shown right now ("system" becomes light or dark)
  setTheme: (theme: Theme) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function readStored(): Theme {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === "light" || value === "dark" ? value : "system"
  } catch {
    return "system"
  }
}

function systemPrefersDark() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches === true
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStored)
  const [systemDark, setSystemDark] = useState(systemPrefersDark)

  // Follow the operating system when it switches between light and dark.
  useEffect(() => {
    const media = window.matchMedia?.("(prefers-color-scheme: dark)")
    if (!media) return
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches)
    media.addEventListener("change", onChange)
    return () => media.removeEventListener("change", onChange)
  }, [])

  const resolvedTheme: Resolved = theme === "system" ? (systemDark ? "dark" : "light") : theme

  useEffect(() => {
    document.documentElement.classList.toggle("dark", resolvedTheme === "dark")
  }, [resolvedTheme])

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next)
    try {
      if (next === "system") localStorage.removeItem(STORAGE_KEY)
      else localStorage.setItem(STORAGE_KEY, next)
    } catch {
      /* not saved, but the choice still applies until the page is closed */
    }
  }, [])

  const value = useMemo(() => ({ theme, resolvedTheme, setTheme }), [theme, resolvedTheme, setTheme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>")
  return ctx
}
