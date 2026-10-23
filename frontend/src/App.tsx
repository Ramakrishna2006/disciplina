import { Route, Routes } from "react-router"

import { GuestOnlyRoute, ProtectedRoute } from "@/components/RouteGuards"
import { AppLayout } from "@/layouts/AppLayout"
import { PublicLayout } from "@/layouts/PublicLayout"
import { DashboardPage } from "@/pages/DashboardPage"
import { LandingPage } from "@/pages/LandingPage"
import { LoginPage } from "@/pages/LoginPage"
import { NotFoundPage } from "@/pages/NotFoundPage"
import { RegisterPage } from "@/pages/RegisterPage"

/** Every page and who may see it. Stage 5 adds the pages under /app. */
export function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<LandingPage />} />
        <Route element={<GuestOnlyRoute />}>
          <Route path="login" element={<LoginPage />} />
          <Route path="register" element={<RegisterPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route path="app" element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
