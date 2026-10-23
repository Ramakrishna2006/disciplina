import { useState, type ReactNode } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { CircleAlertIcon, LoaderCircleIcon } from "lucide-react"
import { useNavigate } from "react-router"
import { toast } from "sonner"

import { FormField } from "@/components/FormField"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { applyServerError } from "@/lib/forms"
import { experimentSchema, type ExperimentValues } from "@/lib/schemas"
import { cn } from "@/lib/utils"
import { api } from "@/services/api"
import type { AppConfig } from "@/types/api"

const FIELDS = ["name", "description", "pretrain_steps", "finetune_steps", "lora_rank", "replay", "seed"] as const

export const DEFAULT_EXPERIMENT: ExperimentValues = {
  name: "",
  description: "",
  pretrain_steps: 150,
  finetune_steps: 60,
  lora_rank: 8,
  replay: true,
  seed: 0,
}

/**
 * The "New experiment" form. Pick a preset (quick, short, full) or set the steps yourself, then
 * change one thing at a time (LoRA rank, replay, seed) to see what it does.
 */
export function NewExperimentDialog({
  trigger,
  config,
  initial,
}: {
  trigger: ReactNode
  config: AppConfig | undefined
  initial?: Partial<ExperimentValues>
}) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ExperimentValues>({
    resolver: zodResolver(experimentSchema),
    defaultValues: { ...DEFAULT_EXPERIMENT, ...initial },
  })
  const steps = [watch("pretrain_steps"), watch("finetune_steps")]

  async function onSubmit(values: ExperimentValues) {
    setFormError(null)
    try {
      const exp = await api.createExperiment(values)
      toast.success(`"${exp.name}" is queued. Training starts in a moment.`)
      setOpen(false)
      navigate(`/app/experiments/${exp.id}`)
    } catch (e) {
      setFormError(applyServerError(e, setError, FIELDS))
    }
  }

  const disabled = config ? !config.training_enabled : false

  return (
    <Dialog
      open={open}
      onOpenChange={(next: boolean) => {
        if (isSubmitting) return
        if (next) {
          reset({ ...DEFAULT_EXPERIMENT, ...initial })
          setFormError(null)
        }
        setOpen(next)
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-xl">
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-5">
          <DialogHeader>
            <DialogTitle>New experiment</DialogTitle>
            <DialogDescription>
              Trains the whole recipe on this computer: tokenizer, pre-training, then full and LoRA fine-tuning, then the
              test. You can leave the page; it keeps training.
            </DialogDescription>
          </DialogHeader>

          {disabled && (
            <Alert>
              <CircleAlertIcon />
              <AlertDescription>
                Training is switched off on this server. Run Disciplina Studio on your own computer to train.
              </AlertDescription>
            </Alert>
          )}
          {formError && (
            <Alert variant="destructive">
              <CircleAlertIcon />
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          )}

          <FormField label="Name" error={errors.name?.message} placeholder="e.g. LoRA rank 4, no replay" {...register("name")} />
          <div className="grid gap-2">
            <Label htmlFor="exp-description">Description (optional)</Label>
            <Textarea id="exp-description" rows={2} maxLength={500} placeholder="What are you testing?" {...register("description")} />
            {errors.description && <p className="text-sm text-destructive">{errors.description.message}</p>}
          </div>

          <fieldset className="grid gap-2">
            <legend className="mb-2 text-sm font-medium">Length</legend>
            <div className="grid grid-cols-3 gap-2">
              {config?.presets.map((p) => {
                const active = steps[0] === p.pretrain_steps && steps[1] === p.finetune_steps
                return (
                  <button
                    key={p.name}
                    type="button"
                    aria-pressed={active}
                    onClick={() => {
                      setValue("pretrain_steps", p.pretrain_steps, { shouldValidate: true })
                      setValue("finetune_steps", p.finetune_steps, { shouldValidate: true })
                    }}
                    className={cn(
                      "rounded-md border p-2 text-left text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                      active ? "border-primary bg-accent text-accent-foreground" : "hover:bg-muted"
                    )}
                  >
                    <span className="block font-medium capitalize">{p.name}</span>
                    <span className="block text-xs text-muted-foreground">{p.minutes ? `${p.minutes} min` : `${p.pretrain_steps} steps`}</span>
                  </button>
                )
              })}
            </div>
          </fieldset>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              label="Pre-training steps"
              type="number"
              inputMode="numeric"
              hint="50 to 5,000"
              error={errors.pretrain_steps?.message}
              {...register("pretrain_steps", { valueAsNumber: true })}
            />
            <FormField
              label="Fine-tuning steps"
              type="number"
              inputMode="numeric"
              hint="20 to 2,000 (each, full and LoRA)"
              error={errors.finetune_steps?.message}
              {...register("finetune_steps", { valueAsNumber: true })}
            />
            <FormField
              label="LoRA rank"
              type="number"
              inputMode="numeric"
              hint="1 to 32. Rank 8 trains 49,152 weights"
              error={errors.lora_rank?.message}
              {...register("lora_rank", { valueAsNumber: true })}
            />
            <FormField
              label="Seed"
              type="number"
              inputMode="numeric"
              hint="0 to 9,999. Same seed, same result"
              error={errors.seed?.message}
              {...register("seed", { valueAsNumber: true })}
            />
          </div>

          <label className="flex items-start gap-3 text-sm">
            <input type="checkbox" className="mt-0.5 size-4 accent-primary" {...register("replay")} />
            <span>
              <span className="font-medium">Replay pre-training text while fine-tuning</span>
              <span className="block text-muted-foreground">
                Mixes in some plain text so the model does not forget it (“catastrophic forgetting”). Switch it off to see
                the difference.
              </span>
            </span>
          </label>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || disabled}>
              {isSubmitting && <LoaderCircleIcon className="animate-spin" />}
              Start training
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
