import { Link, Outlet } from "react-router"

import { Logo } from "@/components/Logo"
import { ThemeToggle } from "@/components/ThemeToggle"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/hooks/useAuth"

export function PublicLayout() {
  const { status } = useAuth()
  return (
    <div className="flex min-h-svh flex-col">
      <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1200px] items-center gap-2 px-4">
          <Logo />
          <div className="ml-auto flex items-center gap-1">
            <ThemeToggle />
            {status === "signed-in" ? (
              <Button asChild size="sm">
                <Link to="/app">Open the app</Link>
              </Button>
            ) : (
              <>
                <Button asChild variant="ghost" size="sm">
                  <Link to="/login">Sign in</Link>
                </Button>
                <Button asChild size="sm">
                  <Link to="/register">Create account</Link>
                </Button>
              </>
            )}
          </div>
        </div>
      </header>
      <main id="main" className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-2 px-4 py-6 text-sm text-muted-foreground">
          <span>Disciplina: a language model trained from scratch in pure NumPy. MIT licence.</span>
          <a
            className="underline-offset-4 hover:text-foreground hover:underline"
            href="https://github.com/Ramakrishna2006/disciplina"
            target="_blank"
            rel="noreferrer"
          >
            Source on GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
