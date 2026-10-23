import { useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { CircleAlertIcon, LoaderCircleIcon } from "lucide-react"
import { useForm } from "react-hook-form"
import { Link, useNavigate } from "react-router"
import { toast } from "sonner"

import { FormField } from "@/components/FormField"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/hooks/useAuth"
import { applyServerError } from "@/lib/forms"
import { PASSWORD_MIN, registerSchema, type RegisterValues } from "@/lib/schemas"

import { AuthCard } from "./AuthCard"

export function RegisterPage() {
  const { register: createAccount } = useAuth()
  const navigate = useNavigate()
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(registerSchema),
    defaultValues: { name: "", email: "", password: "", confirmPassword: "" },
  })

  async function onSubmit(values: RegisterValues) {
    setFormError(null)
    try {
      const user = await createAccount(values.name, values.email, values.password)
      toast.success(`Welcome, ${user.name}!`)
      navigate("/app", { replace: true })
    } catch (error) {
      setFormError(applyServerError(error, setError, ["name", "email", "password"]))
    }
  }

  return (
    <AuthCard
      title="Create your account"
      description="Free. Used only to keep your experiments and chats."
      footer={
        <span>
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-primary underline-offset-4 hover:underline">
            Sign in
          </Link>
        </span>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-4">
        {formError && (
          <Alert variant="destructive">
            <CircleAlertIcon />
            <AlertDescription>{formError}</AlertDescription>
          </Alert>
        )}
        <FormField label="Name" autoComplete="name" autoFocus error={errors.name?.message} {...register("name")} />
        <FormField
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register("email")}
        />
        <FormField
          label="Password"
          type="password"
          autoComplete="new-password"
          hint={`At least ${PASSWORD_MIN} characters. A short sentence is easy to remember.`}
          error={errors.password?.message}
          {...register("password")}
        />
        <FormField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          error={errors.confirmPassword?.message}
          {...register("confirmPassword")}
        />
        <Button type="submit" disabled={isSubmitting} className="mt-2">
          {isSubmitting && <LoaderCircleIcon className="animate-spin" />}
          {isSubmitting ? "Creating your account..." : "Create account"}
        </Button>
      </form>
    </AuthCard>
  )
}
