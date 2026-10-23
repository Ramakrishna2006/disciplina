import { useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { CircleAlertIcon, LoaderCircleIcon } from "lucide-react"
import { useForm } from "react-hook-form"
import { Link, useNavigate, useSearchParams } from "react-router"

import { FormField } from "@/components/FormField"
import { safeNext } from "@/components/RouteGuards"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/hooks/useAuth"
import { applyServerError } from "@/lib/forms"
import { loginSchema, type LoginValues } from "@/lib/schemas"

import { AuthCard } from "./AuthCard"

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } })

  async function onSubmit(values: LoginValues) {
    setFormError(null)
    try {
      await login(values.email, values.password)
      navigate(safeNext(params.get("next")), { replace: true })
    } catch (error) {
      setFormError(applyServerError(error, setError, ["email", "password"]))
    }
  }

  return (
    <AuthCard
      title="Sign in"
      description="Welcome back to Disciplina Studio."
      footer={
        <span>
          New here?{" "}
          <Link to="/register" className="font-medium text-primary underline-offset-4 hover:underline">
            Create an account
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
        <FormField
          label="Email"
          type="email"
          autoComplete="email"
          autoFocus
          error={errors.email?.message}
          {...register("email")}
        />
        <FormField
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register("password")}
        />
        <Button type="submit" disabled={isSubmitting} className="mt-2">
          {isSubmitting && <LoaderCircleIcon className="animate-spin" />}
          {isSubmitting ? "Signing in..." : "Sign in"}
        </Button>
      </form>
    </AuthCard>
  )
}
