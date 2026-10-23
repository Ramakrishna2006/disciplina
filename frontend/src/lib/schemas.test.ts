import { describe, expect, it } from "vitest"
import type { z } from "zod"

import { loginSchema, registerSchema } from "./schemas"

const valid = { name: "Asha", email: "asha@example.com", password: "correct horse", confirmPassword: "correct horse" }

/** {field: first message} for the rules the value breaks ({} when it is valid). Zod reports every
 *  broken rule; like the form, we show only the first message for each field. */
function errorsOf(schema: z.ZodType, value: unknown): Record<string, string> {
  const result = schema.safeParse(value)
  const errors: Record<string, string> = {}
  if (!result.success) {
    for (const issue of result.error.issues) errors[String(issue.path[0])] ??= issue.message
  }
  return errors
}

describe("register rules (the same as the backend)", () => {
  it("accepts a valid form and trims the name and email", () => {
    const result = registerSchema.safeParse({ ...valid, name: "  Asha  ", email: " asha@example.com " })
    expect(result.success).toBe(true)
    expect(result.data?.name).toBe("Asha")
    expect(result.data?.email).toBe("asha@example.com")
  })

  const cases: { change: Partial<typeof valid>; field: string; message: string }[] = [
    { change: { name: "   " }, field: "name", message: "Enter your name." },
    { change: { name: "A".repeat(81) }, field: "name", message: "Use at most 80 characters." },
    { change: { email: "" }, field: "email", message: "Enter your email address." },
    { change: { email: "not-an-email" }, field: "email", message: "Enter a valid email address." },
    { change: { password: "short", confirmPassword: "short" }, field: "password", message: "Use at least 10 characters." },
    { change: { password: "x".repeat(129), confirmPassword: "x".repeat(129) }, field: "password", message: "Use at most 128 characters." },
    { change: { confirmPassword: "something else" }, field: "confirmPassword", message: "The passwords do not match." },
  ]

  for (const { change, field, message } of cases) {
    it(`rejects a bad ${field}: ${message}`, () => {
      expect(errorsOf(registerSchema, { ...valid, ...change })[field]).toBe(message)
    })
  }

  it("keeps spaces inside passwords (they count, as on the server)", () => {
    const result = registerSchema.safeParse({ ...valid, password: "  ten chars ", confirmPassword: "  ten chars " })
    expect(result.data?.password).toBe("  ten chars ")
  })
})

describe("login rules", () => {
  it("needs an email and a password, but not a long one (old accounts still sign in)", () => {
    expect(errorsOf(loginSchema, { email: "", password: "" })).toEqual({
      email: "Enter your email address.",
      password: "Enter your password.",
    })
    expect(loginSchema.safeParse({ email: "a@b.co", password: "x" }).success).toBe(true)
  })
})
