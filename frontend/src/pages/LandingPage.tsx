import { ArrowRightIcon, FlaskConicalIcon, MessageSquareIcon, WaypointsIcon } from "lucide-react"
import { Link } from "react-router"

import { Button } from "@/components/ui/button"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/hooks/useAuth"

// Real numbers from the published run (artifacts/results.json), not marketing.
const FACTS = [
  { value: "512,544", label: "parameters, every gradient written by hand" },
  { value: "60 / 60", label: "questions right about people never seen in Q&A form" },
  { value: "9.6%", label: "of the weights trained by LoRA, with the same accuracy" },
  { value: "0", label: "deep-learning frameworks: only NumPy" },
]

const FEATURES = [
  {
    icon: MessageSquareIcon,
    title: "Ask the model",
    text: "Chat with the base, fully fine-tuned and LoRA models side by side, and change temperature and top-k.",
  },
  {
    icon: WaypointsIcon,
    title: "Look inside",
    text: "See how text becomes tokens, and how the model groups cities, jobs and foods on its own.",
  },
  {
    icon: FlaskConicalIcon,
    title: "Run experiments",
    text: "Change the training settings, watch the loss fall live, and compare runs on the same tests.",
  },
]

export function LandingPage() {
  const { status } = useAuth()
  const signedIn = status === "signed-in"
  return (
    <div className="mx-auto max-w-[1200px] px-4">
      <section className="py-16 md:py-24">
        <p className="mb-4 text-sm font-medium text-primary">Disciplina: Latin for training</p>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance md:text-5xl">
          A language model you can watch learn.
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-muted-foreground text-pretty">
          A GPT-style transformer built from scratch in NumPy, with its tokenizer, training, LoRA fine-tuning and
          evaluation all in the open. Disciplina Studio lets you talk to it, look inside it and train your own runs.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link to={signedIn ? "/app" : "/register"}>
              {signedIn ? "Open the app" : "Create a free account"} <ArrowRightIcon />
            </Link>
          </Button>
          {!signedIn && (
            <Button asChild size="lg" variant="outline">
              <Link to="/login">Sign in</Link>
            </Button>
          )}
        </div>
      </section>

      <section aria-label="Results" className="grid gap-4 border-y py-10 sm:grid-cols-2 lg:grid-cols-4">
        {FACTS.map((fact) => (
          <div key={fact.label}>
            <div className="font-mono text-3xl font-semibold tracking-tight">{fact.value}</div>
            <div className="mt-1 text-sm text-muted-foreground">{fact.label}</div>
          </div>
        ))}
      </section>

      <section aria-label="What you can do" className="grid gap-4 py-16 md:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <Card key={title}>
            <CardHeader>
              <Icon className="mb-2 size-5 text-primary" aria-hidden />
              <CardTitle>{title}</CardTitle>
              <CardDescription>{text}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </section>
    </div>
  )
}
