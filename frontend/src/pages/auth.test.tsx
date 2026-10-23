import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { safeNext } from "@/components/RouteGuards"
import { ApiError } from "@/services/api"
import { renderAt } from "@/test/utils"

import { LoginPage } from "./LoginPage"
import { RegisterPage } from "./RegisterPage"

// Replace the real auth hook: these tests check the forms, not the network. vi.mock runs before
// the imports above, so the fake must be created with vi.hoisted (otherwise it does not exist yet).
const auth = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  user: null,
  status: "signed-out",
}))
vi.mock("@/hooks/useAuth", () => ({ useAuth: () => auth }))

beforeEach(() => {
  auth.login.mockReset()
  auth.register.mockReset()
})

const apiError = (status: number, code: string, message: string, fields: Record<string, string> = {}) =>
  new ApiError(status, { code, message, fields })

describe("Sign in", () => {
  it("shows a message under each empty field and does not call the server", async () => {
    const user = userEvent.setup()
    renderAt("/login", "/login", <LoginPage />)
    await user.click(screen.getByRole("button", { name: "Sign in" }))
    expect(await screen.findByText("Enter your email address.")).toBeInTheDocument()
    expect(screen.getByText("Enter your password.")).toBeInTheDocument()
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true")
    expect(auth.login).not.toHaveBeenCalled()
  })

  it("signs in and goes to the page you came from", async () => {
    auth.login.mockResolvedValue({ id: 1, name: "Asha" })
    const user = userEvent.setup()
    renderAt("/login?next=%2Fapp%2Fexperiments", "/login", <LoginPage />)
    await user.type(screen.getByLabelText("Email"), "  asha@example.com ")
    await user.type(screen.getByLabelText("Password"), "correct horse battery")
    await user.click(screen.getByRole("button", { name: "Sign in" }))
    expect(await screen.findByText("Landed in the app")).toBeInTheDocument()
    expect(auth.login).toHaveBeenCalledWith("asha@example.com", "correct horse battery") // email trimmed
  })

  it("shows the server's message for a wrong password", async () => {
    auth.login.mockRejectedValue(apiError(401, "invalid_credentials", "Wrong email or password."))
    const user = userEvent.setup()
    renderAt("/login", "/login", <LoginPage />)
    await user.type(screen.getByLabelText("Email"), "asha@example.com")
    await user.type(screen.getByLabelText("Password"), "wrong")
    await user.click(screen.getByRole("button", { name: "Sign in" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong email or password.")
  })

  it("can show the password while typing it", async () => {
    const user = userEvent.setup()
    renderAt("/login", "/login", <LoginPage />)
    const field = screen.getByLabelText("Password")
    expect(field).toHaveAttribute("type", "password")
    await user.click(screen.getByRole("button", { name: "Show password" }))
    expect(field).toHaveAttribute("type", "text")
  })

  it("only follows ?next= to pages on this site", () => {
    expect(safeNext("/app/dataset")).toBe("/app/dataset")
    expect(safeNext("//evil.example.com")).toBe("/app")
    expect(safeNext("/\\evil.example.com")).toBe("/app")
    expect(safeNext("https://evil.example.com")).toBe("/app")
    expect(safeNext(null)).toBe("/app")
  })
})

describe("Create account", () => {
  async function fill(values: Partial<Record<"Name" | "Email" | "Password" | "Confirm password", string>>) {
    const user = userEvent.setup()
    renderAt("/register", "/register", <RegisterPage />)
    for (const [label, value] of Object.entries(values)) {
      if (value) await user.type(screen.getByLabelText(label), value)
    }
    await user.click(screen.getByRole("button", { name: "Create account" }))
  }

  it("checks the password length and that both passwords match", async () => {
    await fill({ Name: "Asha", Email: "asha@example.com", Password: "short", "Confirm password": "other" })
    expect(await screen.findByText("Use at least 10 characters.")).toBeInTheDocument()
    expect(screen.getByText("The passwords do not match.")).toBeInTheDocument()
    expect(auth.register).not.toHaveBeenCalled()
  })

  it("puts the server's 'email already registered' message under the email field", async () => {
    auth.register.mockRejectedValue(
      apiError(409, "email_taken", "An account with this email already exists.", { email: "This email is already registered." })
    )
    await fill({ Name: "Asha", Email: "asha@example.com", Password: "correct horse", "Confirm password": "correct horse" })
    expect(await screen.findByText("This email is already registered.")).toBeInTheDocument()
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true")
  })

  it("explains when the server cannot be reached", async () => {
    auth.register.mockRejectedValue(
      apiError(0, "network_error", "Can't reach the server. Check that it is running and try again.")
    )
    await fill({ Name: "Asha", Email: "asha@example.com", Password: "correct horse", "Confirm password": "correct horse" })
    expect(await screen.findByRole("alert")).toHaveTextContent("Can't reach the server")
  })

  it("creates the account and opens the app", async () => {
    auth.register.mockResolvedValue({ id: 1, name: "Asha" })
    await fill({ Name: " Asha ", Email: "asha@example.com", Password: "correct horse", "Confirm password": "correct horse" })
    expect(await screen.findByText("Landed in the app")).toBeInTheDocument()
    expect(auth.register).toHaveBeenCalledWith("Asha", "asha@example.com", "correct horse")
  })
})
