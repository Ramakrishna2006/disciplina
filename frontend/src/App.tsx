import { lazy, Suspense, type ComponentType, type ReactNode } from "react"
import { Route, Routes } from "react-router"

import { LoadingRows } from "@/components/PageState"
import { GuestOnlyRoute, ProtectedRoute } from "@/components/RouteGuards"
import { AppLayout } from "@/layouts/AppLayout"
import { PublicLayout } from "@/layouts/PublicLayout"
import { LandingPage } from "@/pages/LandingPage"
import { LoginPage } from "@/pages/LoginPage"
import { NotFoundPage } from "@/pages/NotFoundPage"
import { RegisterPage } from "@/pages/RegisterPage"

// The pages inside the app are loaded only when you open them ("code-splitting"), so the first
// visit downloads less. Each lazy() becomes its own small JavaScript file in the build.
const page = <K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })))

const DashboardPage = page(() => import("@/pages/DashboardPage"), "DashboardPage")
const PlaygroundPage = page(() => import("@/pages/PlaygroundPage"), "PlaygroundPage")
const TokenizerPage = page(() => import("@/pages/TokenizerPage"), "TokenizerPage")
const EmbeddingsPage = page(() => import("@/pages/EmbeddingsPage"), "EmbeddingsPage")
const DatasetPage = page(() => import("@/pages/DatasetPage"), "DatasetPage")
const ExperimentsPage = page(() => import("@/pages/ExperimentsPage"), "ExperimentsPage")
const ExperimentDetailPage = page(() => import("@/pages/ExperimentDetailPage"), "ExperimentDetailPage")
const ComparePage = page(() => import("@/pages/ComparePage"), "ComparePage")
const ActivityPage = page(() => import("@/pages/ActivityPage"), "ActivityPage")
const SettingsPage = page(() => import("@/pages/SettingsPage"), "SettingsPage")
const HelpPage = page(() => import("@/pages/HelpPage"), "HelpPage")

function Loading() {
  return <LoadingRows rows={4} label="Loading the page" />
}

/** Every page and who may see it. */
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
          <Route index element={<Lazy page={<DashboardPage />} />} />
          <Route path="playground" element={<Lazy page={<PlaygroundPage />} />} />
          <Route path="tokenizer" element={<Lazy page={<TokenizerPage />} />} />
          <Route path="embeddings" element={<Lazy page={<EmbeddingsPage />} />} />
          <Route path="dataset" element={<Lazy page={<DatasetPage />} />} />
          <Route path="experiments" element={<Lazy page={<ExperimentsPage />} />} />
          <Route path="experiments/:id" element={<Lazy page={<ExperimentDetailPage />} />} />
          <Route path="compare" element={<Lazy page={<ComparePage />} />} />
          <Route path="activity" element={<Lazy page={<ActivityPage />} />} />
          <Route path="settings" element={<Lazy page={<SettingsPage />} />} />
          <Route path="help" element={<Lazy page={<HelpPage />} />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

function Lazy({ page }: { page: ReactNode }) {
  return <Suspense fallback={<Loading />}>{page}</Suspense>
}
