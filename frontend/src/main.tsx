import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router"

import "@fontsource-variable/inter"
import "@fontsource-variable/jetbrains-mono"
import "./index.css"

import { App } from "./App"
import { Toaster } from "./components/ui/sonner"
import { AuthProvider } from "./hooks/useAuth"
import { ThemeProvider } from "./hooks/useTheme"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <App />
          <Toaster position="top-center" />
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  </StrictMode>
)
