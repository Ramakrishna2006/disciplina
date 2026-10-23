import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

/** Join class names, letting later Tailwind classes win over earlier ones (shadcn/ui helper). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
