import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { CircleAlertIcon, LoaderCircleIcon } from "lucide-react"
import { useNavigate } from "react-router"
import { toast } from "sonner"

import { FormField } from "@/components/FormField"
import { PageHeader } from "@/components/PageState"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { NativeSelect } from "@/components/ui/native-select"
import { useAuth } from "@/hooks/useAuth"
import { useTheme } from "@/hooks/useTheme"
import { applyServerError } from "@/lib/forms"
import { passwordSchema, profileSchema, type PasswordValues, type ProfileValues } from "@/lib/schemas"
import { api } from "@/services/api"
import type { User } from "@/types/api"

function ProfileCard({ user }: { user: User }) {
  const { updateUser } = useAuth()
  const { setTheme } = useTheme()
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    watch,
    reset,
    setError,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      name: user.name,
      theme: user.theme,
      default_model: user.default_model,
      default_temperature: user.default_temperature,
    },
  })
  const temperature = watch("default_temperature")

  async function onSubmit(values: ProfileValues) {
    setFormError(null)
    try {
      const saved = await api.updateProfile(values)
      updateUser(saved)
      setTheme(saved.theme)
      reset(values)
      toast.success("Settings saved.")
    } catch (e) {
      setFormError(applyServerError(e, setError, ["name", "theme", "default_model", "default_temperature"]))
    }
  }

  return (
    <Card>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-6">
        <CardHeader>
          <CardTitle>Profile and preferences</CardTitle>
          <CardDescription>Signed in as {user.email}. The email address cannot be changed.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          {formError && (
            <Alert variant="destructive" className="sm:col-span-2">
              <CircleAlertIcon />
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          )}
          <FormField label="Name" autoComplete="name" error={errors.name?.message} {...register("name")} />
          <div className="grid gap-2">
            <Label htmlFor="set-theme">Theme</Label>
            <NativeSelect id="set-theme" {...register("theme")}>
              <option value="system">Same as my computer</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </NativeSelect>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="set-model">Playground starts with</Label>
            <NativeSelect id="set-model" {...register("default_model")}>
              <option value="lora">LoRA</option>
              <option value="full">Full fine-tune</option>
              <option value="base">Base</option>
            </NativeSelect>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="set-temp">
              Default temperature <span className="font-mono text-muted-foreground">{Number(temperature).toFixed(1)}</span>
            </Label>
            <input
              id="set-temp"
              type="range"
              min={0}
              max={2}
              step={0.1}
              className="h-9 accent-primary"
              {...register("default_temperature", { valueAsNumber: true })}
            />
          </div>
        </CardContent>
        <CardFooter className="justify-end">
          <Button type="submit" disabled={isSubmitting || !isDirty}>
            {isSubmitting && <LoaderCircleIcon className="animate-spin" />}
            Save
          </Button>
        </CardFooter>
      </form>
    </Card>
  )
}

function PasswordCard() {
  const { updateUser } = useAuth()
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  })

  async function onSubmit(values: PasswordValues) {
    setFormError(null)
    try {
      updateUser(await api.changePassword(values.current_password, values.new_password))
      reset()
      toast.success("Password changed. Your other devices are signed out.")
    } catch (e) {
      setFormError(applyServerError(e, setError, ["current_password", "new_password"]))
    }
  }

  return (
    <Card>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-6">
        <CardHeader>
          <CardTitle>Password</CardTitle>
          <CardDescription>After a change, every other device where you are signed in is signed out.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {formError && (
            <Alert variant="destructive">
              <CircleAlertIcon />
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          )}
          <FormField label="Current password" type="password" autoComplete="current-password" error={errors.current_password?.message} {...register("current_password")} />
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="New password" type="password" autoComplete="new-password" hint="At least 10 characters" error={errors.new_password?.message} {...register("new_password")} />
            <FormField label="Repeat the new password" type="password" autoComplete="new-password" error={errors.confirm?.message} {...register("confirm")} />
          </div>
        </CardContent>
        <CardFooter className="justify-end">
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting && <LoaderCircleIcon className="animate-spin" />}
            Change password
          </Button>
        </CardFooter>
      </form>
    </Card>
  )
}

function DeleteAccountCard() {
  const { forget } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      await api.deleteAccount(password)
      forget()
      toast.success("Your account and all its data are deleted.")
      navigate("/", { replace: true })
    } catch (e) {
      setError(applyServerError(e, () => {}, []) ?? "Your password is not correct.")
      setBusy(false)
    }
  }

  return (
    <Card className="border-destructive/40">
      <CardHeader>
        <CardTitle>Delete account</CardTitle>
        <CardDescription>
          Deletes your account, experiments, trained models, conversations and activity. This cannot be undone.
        </CardDescription>
      </CardHeader>
      <CardFooter className="justify-end">
        <Dialog
          open={open}
          onOpenChange={(next: boolean) => {
            if (busy) return
            setOpen(next)
            setPassword("")
            setError(null)
          }}
        >
          <DialogTrigger asChild>
            <Button variant="destructive">Delete my account</Button>
          </DialogTrigger>
          <DialogContent>
            <form
              className="grid gap-4"
              onSubmit={(e) => {
                e.preventDefault()
                void confirm()
              }}
            >
              <DialogHeader>
                <DialogTitle>Delete your account?</DialogTitle>
                <DialogDescription>Type your password to confirm. Everything you made here is deleted.</DialogDescription>
              </DialogHeader>
              <FormField label="Password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} error={error ?? undefined} />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={busy}>
                  Cancel
                </Button>
                <Button type="submit" variant="destructive" disabled={busy || !password}>
                  {busy && <LoaderCircleIcon className="animate-spin" />}
                  Delete everything
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </CardFooter>
    </Card>
  )
}

export function SettingsPage() {
  const { user } = useAuth()
  if (!user) return null
  return (
    <div className="grid max-w-3xl gap-6">
      <PageHeader title="Settings" description="Your profile, preferences and password." />
      <ProfileCard user={user} />
      <PasswordCard />
      <DeleteAccountCard />
    </div>
  )
}
