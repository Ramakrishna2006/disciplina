import { screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { NewExperimentDialog } from "@/components/NewExperimentDialog"
import { Button } from "@/components/ui/button"
import { ApiError } from "@/services/api"
import { renderAt } from "@/test/utils"
import type { AppConfig } from "@/types/api"

import { PlaygroundPage } from "./PlaygroundPage"

// These tests check the pages, not the network: the API functions they use are replaced by fakes.
const api = vi.hoisted(() => ({
  sessions: vi.fn(),
  session: vi.fn(),
  chat: vi.fn(),
  createExperiment: vi.fn(),
}))
vi.mock("@/services/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/services/api")>()),
  api,
}))
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ user: { id: 1, name: "Asha", default_model: "lora", default_temperature: 0 }, status: "signed-in" }),
}))

const EMPTY_PAGE = { items: [], meta: { page: 1, per_page: 20, total: 0, pages: 1 } }

beforeEach(() => {
  for (const fn of Object.values(api)) fn.mockReset()
  api.sessions.mockResolvedValue(EMPTY_PAGE)
})

describe("Playground", () => {
  it("sends a question and shows the answer", async () => {
    const messages = [
      { id: 1, role: "user", content: "Where does Leela live?", model: "lora", temperature: 0, top_k: null, latency_ms: null, created_at: "2026-01-01T00:00:00Z" },
      { id: 2, role: "assistant", content: "Surat", model: "lora", temperature: 0, top_k: null, latency_ms: 12, created_at: "2026-01-01T00:00:00Z" },
    ]
    api.chat.mockResolvedValue({ session_id: 5, reply: "Surat", latency_ms: 12, tokens: 2, messages })
    // After the first answer the page opens the new conversation, which the server returns like this:
    api.session.mockResolvedValue({
      session: { id: 5, title: "Where does Leela live?", model: "lora", created_at: "", updated_at: "" },
      messages,
    })
    const user = userEvent.setup()
    renderAt("/app/playground", "/app/playground", <PlaygroundPage />)

    await user.type(screen.getByLabelText("Message"), "Where does Leela live?")
    await user.click(screen.getByRole("button", { name: "Send" }))

    expect(await screen.findByText("Surat")).toBeInTheDocument()
    expect(api.chat).toHaveBeenCalledWith({
      message: "Where does Leela live?",
      model: "lora",
      temperature: 0,
      top_k: null,
      session_id: undefined,
    })
    expect(screen.getByLabelText("Message")).toHaveValue("") // cleared after sending
  })

  it("does not send an empty message, and Enter sends", async () => {
    api.chat.mockResolvedValue({ session_id: 1, reply: "x", latency_ms: 1, tokens: 1, messages: [] })
    api.session.mockResolvedValue({ session: { id: 1, title: "x", model: "lora", created_at: "", updated_at: "" }, messages: [] })
    const user = userEvent.setup()
    renderAt("/app/playground", "/app/playground", <PlaygroundPage />)
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled()
    await user.type(screen.getByLabelText("Message"), "   ")
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled()
    await user.type(screen.getByLabelText("Message"), "Leela lives in{Enter}")
    expect(api.chat).toHaveBeenCalledTimes(1)
  })

  it("starts with a question passed from the Dataset page", async () => {
    renderAt("/app/playground?ask=Where%20does%20Ravi%20live%3F", "/app/playground", <PlaygroundPage />)
    expect(screen.getByLabelText("Message")).toHaveValue("Where does Ravi live?")
  })
})

const CONFIG: AppConfig = {
  app: "Disciplina Studio",
  version: "0.5.0",
  training_enabled: true,
  presets: [
    { name: "quick", pretrain_steps: 150, finetune_steps: 60, minutes: "4-7" },
    { name: "short", pretrain_steps: 600, finetune_steps: 150, minutes: "8-12" },
  ],
  limits: {},
  models: [],
}

function renderDialog(config: AppConfig = CONFIG) {
  return renderAt(
    "/app/experiments",
    "/app/experiments",
    <NewExperimentDialog config={config} trigger={<Button>New experiment</Button>} />
  )
}

describe("New experiment", () => {
  it("uses a preset and starts training", async () => {
    api.createExperiment.mockResolvedValue({ id: 9, name: "Short run" })
    const user = userEvent.setup()
    renderDialog()
    await user.click(screen.getByRole("button", { name: "New experiment" }))
    const dialog = await screen.findByRole("dialog")
    await user.type(within(dialog).getByLabelText("Name"), "Short run")
    await user.click(within(dialog).getByRole("button", { name: /short/i }))
    await user.click(within(dialog).getByLabelText(/Replay pre-training text/))
    await user.click(within(dialog).getByRole("button", { name: "Start training" }))

    expect(await screen.findByText("Landed in the app")).toBeInTheDocument() // went to the new experiment
    expect(api.createExperiment).toHaveBeenCalledWith({
      name: "Short run",
      description: "",
      pretrain_steps: 600,
      finetune_steps: 150,
      lora_rank: 8,
      replay: false,
      seed: 0,
    })
  })

  it("checks the limits before asking the server", async () => {
    const user = userEvent.setup()
    renderDialog()
    await user.click(screen.getByRole("button", { name: "New experiment" }))
    const dialog = await screen.findByRole("dialog")
    await user.clear(within(dialog).getByLabelText("LoRA rank"))
    await user.type(within(dialog).getByLabelText("LoRA rank"), "64")
    await user.click(within(dialog).getByRole("button", { name: "Start training" }))
    expect(await within(dialog).findByText("Give the experiment a name.")).toBeInTheDocument()
    expect(within(dialog).getByText("Use at most 32.")).toBeInTheDocument()
    expect(api.createExperiment).not.toHaveBeenCalled()
  })

  it("shows the server's reason when it refuses", async () => {
    api.createExperiment.mockRejectedValue(
      new ApiError(409, { code: "experiment_active", message: "You already have an experiment queued or training.", fields: {} })
    )
    const user = userEvent.setup()
    renderDialog()
    await user.click(screen.getByRole("button", { name: "New experiment" }))
    const dialog = await screen.findByRole("dialog")
    await user.type(within(dialog).getByLabelText("Name"), "Again")
    await user.click(within(dialog).getByRole("button", { name: "Start training" }))
    expect(await within(dialog).findByText("You already have an experiment queued or training.")).toBeInTheDocument()
  })

  it("explains when training is switched off", async () => {
    const user = userEvent.setup()
    renderDialog({ ...CONFIG, training_enabled: false })
    await user.click(screen.getByRole("button", { name: "New experiment" }))
    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).getByText(/Training is switched off/)).toBeInTheDocument()
    expect(within(dialog).getByRole("button", { name: "Start training" })).toBeDisabled()
  })
})
