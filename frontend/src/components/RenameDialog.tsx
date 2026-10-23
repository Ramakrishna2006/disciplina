import { useId, useState, type FormEvent, type ReactNode } from "react"
import { LoaderCircleIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

/** A small form in a dialog to rename something (1-80 characters, like the backend). */
export function RenameDialog({
  trigger,
  title,
  value,
  onSave,
}: {
  trigger: ReactNode
  title: string
  value: string
  onSave: (name: string) => Promise<unknown>
}) {
  const id = useId()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(value)
  const [busy, setBusy] = useState(false)
  const clean = name.trim().replace(/\s+/g, " ")
  const error = clean.length === 0 ? "Enter a name." : clean.length > 80 ? "Use at most 80 characters." : null

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (error) return
    setBusy(true)
    try {
      await onSave(clean)
      setOpen(false)
    } catch {
      // onSave showed the error; keep the dialog open
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next: boolean) => {
        if (busy) return
        if (next) setName(value)
        setOpen(next)
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>Up to 80 characters.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor={id}>Name</Label>
            <Input
              id={id}
              value={name}
              onChange={(e) => setName(e.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? `${id}-error` : undefined}
              autoFocus
            />
            {error && (
              <p id={`${id}-error`} className="text-sm text-destructive">
                {error}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy || !!error}>
              {busy && <LoaderCircleIcon className="animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
