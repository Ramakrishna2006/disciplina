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

// ----------------------------------------------------------------------------- experiments
// The same limits as backend/app/models/experiment.py (LIMITS) and schemas/studio.py.
const whole = (label: string, min: number, max: number) =>
  z
    .number({ error: `Enter a number for ${label}.` })
    .int(`${label} must be a whole number.`)
    .min(min, `Use at least ${min}.`)
    .max(max, `Use at most ${max}.`)

export const experimentSchema = z.object({
  name: z.string().trim().min(1, "Give the experiment a name.").max(80, "Use at most 80 characters."),
  description: z.string().trim().max(500, "Use at most 500 characters."),
  pretrain_steps: whole("Pre-training steps", 50, 5000),
  finetune_steps: whole("Fine-tuning steps", 20, 2000),
  lora_rank: whole("LoRA rank", 1, 32),
  replay: z.boolean(),
  seed: whole("Seed", 0, 9999),
})

export type ExperimentValues = z.infer<typeof experimentSchema>

// ----------------------------------------------------------------------------- settings
export const profileSchema = z.object({
  name: z.string().trim().min(1, "Enter your name.").max(80, "Use at most 80 characters."),
  theme: z.enum(["system", "light", "dark"]),
  default_model: z.enum(["base", "full", "lora"]),
  default_temperature: z.number().min(0, "Use 0 to 2.").max(2, "Use 0 to 2."),
})

export const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Enter your current password."),
    new_password: z
      .string()
      .min(PASSWORD_MIN, `Use at least ${PASSWORD_MIN} characters.`)
      .max(PASSWORD_MAX, `Use at most ${PASSWORD_MAX} characters.`),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, { path: ["confirm"], message: "The passwords do not match." })
  .refine((v) => v.new_password !== v.current_password, {
    path: ["new_password"],
    message: "Must be different from the current password.",
  })

export type ProfileValues = z.infer<typeof profileSchema>
export type PasswordValues = z.infer<typeof passwordSchema>
