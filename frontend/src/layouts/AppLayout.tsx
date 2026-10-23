import { useState } from "react"
import { MenuIcon } from "lucide-react"
import { NavLink, Outlet, useLocation } from "react-router"

import { Logo } from "@/components/Logo"
import { ThemeToggle } from "@/components/ThemeToggle"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet"
import { UserMenu } from "@/components/UserMenu"
import { cn } from "@/lib/utils"

import { NAV_ITEMS } from "./nav"

function SideNav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="grid gap-1">
      {NAV_ITEMS.map(({ label, to, icon: Icon, ready }) =>
        ready ? (
          <NavLink
            key={to}
            to={to}
            end
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                isActive ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )
            }
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </NavLink>
        ) : (
          // Not built yet: visible so you can see what is coming, but not a fake link.
          <span
            key={to}
            aria-disabled="true"
            title="Coming in stage 5"
            className="flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground/70"
          >
            <Icon className="size-4" aria-hidden />
            {label}
            <span className="ml-auto rounded-sm bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">soon</span>
          </span>
        )
      )}
    </nav>
  )
}

export function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const { pathname } = useLocation()
  const title = NAV_ITEMS.find((item) => item.to === pathname)?.label ?? "Disciplina Studio"

  return (
    <div className="flex min-h-svh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      {/* Sidebar on laptops and desktops */}
      <aside className="sticky top-0 hidden h-svh w-60 shrink-0 flex-col gap-6 border-r bg-sidebar p-4 md:flex">
        <Logo to="/app" className="px-2" />
        <SideNav />
      </aside>

      {/* The same navigation as a slide-in menu on phones */}
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="w-72 gap-6 bg-sidebar p-4">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SheetDescription className="sr-only">Pages of Disciplina Studio</SheetDescription>
          <Logo to="/app" className="px-2" />
          <SideNav onNavigate={() => setMenuOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b bg-background/85 px-4 backdrop-blur">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMenuOpen(true)}
            aria-label="Open navigation"
          >
            <MenuIcon />
          </Button>
          <h1 className="truncate text-base font-semibold">{title}</h1>
          <div className="ml-auto flex items-center gap-1">
            <ThemeToggle />
            <UserMenu />
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-[1200px] flex-1 p-4 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
