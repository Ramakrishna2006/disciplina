import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { LossChart, lossSeries } from "./LossChart"

const METRICS = [
  { phase: "pretrain", step: 0, train_loss: 7.5, val_loss: 7.6 },
  { phase: "pretrain", step: 50, train_loss: 3.1, val_loss: null },
  { phase: "pretrain", step: 99, train_loss: 1.2, val_loss: 1.4 },
  { phase: "full", step: 0, train_loss: 2.0, val_loss: null },
  { phase: "lora", step: 0, train_loss: 2.2, val_loss: null },
  { phase: "lora", step: 19, train_loss: 0.4, val_loss: null },
]

describe("LossChart", () => {
  it("splits metrics into pre-training and fine-tuning series", () => {
    const [train, val] = lossSeries(METRICS, "pretrain")
    expect(train.points).toHaveLength(3)
    expect(val.points).toEqual([
      { x: 0, y: 7.6 },
      { x: 99, y: 1.4 },
    ])
    const [full, lora] = lossSeries(METRICS, "finetune")
    expect([full.name, full.points.length, lora.name, lora.points.length]).toEqual(["Full fine-tune", 1, "LoRA", 2])
  })

  it("is an image with a title and a text summary for screen readers", () => {
    render(<LossChart title="Pre-training loss" series={lossSeries(METRICS, "pretrain")} />)
    const chart = screen.getByRole("img", { name: "Pre-training loss" })
    expect(chart).toHaveAccessibleDescription(/train: from 7\.5 to 1\.2/)
    expect(screen.getByText("validation")).toBeInTheDocument() // legend
  })

  it("shows the numbers as a table on request", async () => {
    const user = userEvent.setup()
    render(<LossChart title="Loss" series={lossSeries(METRICS, "pretrain")} />)
    await user.click(screen.getByRole("button", { name: "Show as table" }))
    const table = screen.getByRole("table")
    expect(table).toHaveTextContent("99")
    expect(table).toHaveTextContent("1.4")
    expect(screen.getByRole("button", { name: "Hide table" })).toHaveAttribute("aria-expanded", "true")
  })

  it("says so when there is nothing to draw yet", () => {
    render(<LossChart title="Loss" series={lossSeries([], "finetune")} />)
    expect(screen.getByText("No points yet.")).toBeInTheDocument()
  })
})
