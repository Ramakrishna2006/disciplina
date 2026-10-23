/**
 * Form rules, written to match the backend exactly (backend/app/schemas/auth.py). The browser
 * checks them first for instant feedback; the server checks them again, because anyone can
 * bypass a browser.
 */
import { z } from "zod"

export const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
export const PASSWORD_MIN = 10
export const PASSWORD_MAX = 128

const email = z
  .string()
  .trim()
  .min(1, "Enter your email address.")
  .max(254, "Email addresses are at most 254 characters.")
  .regex(EMAIL_PATTERN, "Enter a valid email address.")

export const loginSchema = z.object({
  email,
  password: z.string().min(1, "Enter your password.").max(PASSWORD_MAX, "Passwords are at most 128 characters."),
})

export const registerSchema = z
  .object({
    name: z.string().trim().min(1, "Enter your name.").max(80, "Use at most 80 characters."),
    email,
    password: z
      .string()
      .min(PASSWORD_MIN, `Use at least ${PASSWORD_MIN} characters.`)
      .max(PASSWORD_MAX, `Use at most ${PASSWORD_MAX} characters.`),
    confirmPassword: z.string(),
  })
  .refine((v) => v.password === v.confirmPassword, {
    path: ["confirmPassword"],
    message: "The passwords do not match.",
  })

export type LoginValues = z.infer<typeof loginSchema>
export type RegisterValues = z.infer<typeof registerSchema>
