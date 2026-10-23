import type { FieldValues, Path, UseFormSetError } from "react-hook-form"

import { ApiError } from "@/services/api"

/**
 * Put a server error onto a form: messages for known fields appear under those fields, and
 * anything else (wrong password, too many attempts, server unreachable) becomes one message
 * for the whole form. Returns that message, or null if every problem belonged to a field.
 */
export function applyServerError<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  knownFields: readonly Path<T>[]
): string | null {
  if (!(error instanceof ApiError)) return "Something unexpected went wrong. Please try again."
  let placed = false
  for (const [field, message] of Object.entries(error.fields)) {
    if ((knownFields as readonly string[]).includes(field)) {
      setError(field as Path<T>, { type: "server", message })
      placed = true
    }
  }
  if (placed && error.code === "validation_error") return null
  return error.message
}
