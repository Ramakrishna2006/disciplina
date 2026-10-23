import { describe, expect, it } from "vitest"

import { experimentSchema, passwordSchema } from "./schemas"

const GOOD = { name: "Rank 4", description: "", pretrain_steps: 150, finetune_steps: 60, lora_rank: 4, replay: true, seed: 0 }

function firstError(result: { success: boolean; error?: { issues: { path: PropertyKey[]; message: string }[] } }, field: string) {
  return result.error?.issues.find((i) => i.path[0] === field)?.message
}

describe("experiment form rules (same limits as the backend)", () => {
  it("accepts good settings and trims the name", () => {
    const r = experimentSchema.safeParse({ ...GOOD, name: "  Rank 4  " })
    expect(r.success && r.data.name).toBe("Rank 4")
  })

  const cases: [string, Partial<typeof GOOD> | Record<string, unknown>, string][] = [
    ["name", { name: "   " }, "Give the experiment a name."],
    ["pretrain_steps", { pretrain_steps: 49 }, "Use at least 50."],
    ["pretrain_steps", { pretrain_steps: 5001 }, "Use at most 5000."],
    ["finetune_steps", { finetune_steps: 19 }, "Use at least 20."],
    ["lora_rank", { lora_rank: 33 }, "Use at most 32."],
    ["lora_rank", { lora_rank: 2.5 }, "LoRA rank must be a whole number."],
    ["seed", { seed: Number.NaN }, "Enter a number for Seed."],
  ]
  for (const [field, change, message] of cases) {
    it(`rejects ${field} = ${JSON.stringify(Object.values(change)[0])}`, () => {
      expect(firstError(experimentSchema.safeParse({ ...GOOD, ...change }), field)).toBe(message)
    })
  }
})

describe("password change rules", () => {
  it("needs matching, new, long-enough passwords", () => {
    const base = { current_password: "old password 1", new_password: "a brand new one", confirm: "a brand new one" }
    expect(passwordSchema.safeParse(base).success).toBe(true)
    expect(firstError(passwordSchema.safeParse({ ...base, confirm: "different" }), "confirm")).toBe("The passwords do not match.")
    expect(firstError(passwordSchema.safeParse({ ...base, new_password: "short", confirm: "short" }), "new_password")).toBe(
      "Use at least 10 characters."
    )
    const same = { current_password: "old password 1", new_password: "old password 1", confirm: "old password 1" }
    expect(firstError(passwordSchema.safeParse(same), "new_password")).toBe("Must be different from the current password.")
  })
})
