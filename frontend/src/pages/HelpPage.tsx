import type { ReactNode } from "react"
import { Link } from "react-router"

import { PageHeader } from "@/components/PageState"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

const GLOSSARY: [string, string][] = [
  ["Token", "A piece of text the model reads as one unit: a word, part of a word, or a space plus a word. See the Tokenizer page."],
  ["Embedding", "The 96 numbers that stand for one token. Training moves tokens with the same role close together. See the Embeddings page."],
  ["Pre-training", "The first stage: the model reads plain sentences (“Asha lives in Pune.”) and learns to predict the next token."],
  ["Fine-tuning", "The second stage: the model is shown questions and answers, so it learns to answer instead of just continuing text."],
  ["LoRA", "Low-Rank Adaptation. Instead of changing all 512,544 weights, it trains small extra matrices (49,152 weights at rank 8). Rank = how big those matrices are."],
  ["Replay", "Mixing some pre-training text into fine-tuning, so the model does not forget what it read (catastrophic forgetting)."],
  ["Held-out", "People the model never saw a question about. Answering about them shows it really learned, instead of memorising answers."],
  ["Loss", "How wrong the model's predictions are (cross-entropy). It should go down during training. Validation loss is measured on text the model does not train on."],
  ["Perplexity", "e to the power of the loss. 2.5 means the model is as unsure as choosing between 2.5 tokens. Lower is better."],
  ["Temperature", "0: always pick the most likely next token. Higher: pick more randomly. Top-k keeps only the k most likely tokens."],
  ["Seed", "The starting point of the random numbers. The same settings and the same seed train exactly the same model."],
]

const FAQ: [string, ReactNode][] = [
  [
    "Why does the base model not answer questions?",
    "It only learned to continue text. Ask it “Asha lives in” instead of “Where does Asha live?”. The fine-tuned models learned the question format.",
  ],
  [
    "How long does an experiment take?",
    "On a laptop CPU: quick 4–7 minutes, short 8–12, full 30–40. One experiment trains at a time; others wait in the queue. You can close the page.",
  ],
  [
    "Why is training switched off online?",
    "Free hosting has a small, shared CPU. The published models still work in the Playground; train on your own computer with the same app.",
  ],
  [
    "What does “interrupted” mean?",
    "The server stopped while the experiment was training (for example you closed the terminal). Use “Run again” to start it fresh with the same settings.",
  ],
  [
    "Is my data private?",
    <>
      Your experiments and conversations are visible only to you. An admin can publish a finished experiment so everyone
      can compare with it. You can delete everything in <Link to="/app/settings" className="text-primary hover:underline">Settings</Link>.
    </>,
  ],
]

export function HelpPage() {
  return (
    <div className="grid max-w-3xl gap-6">
      <PageHeader title="Help" description="What the words mean, and answers to common questions." />
      <Card>
        <CardHeader>
          <CardTitle>Try this first</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="list-decimal space-y-2 pl-5 text-sm">
            <li>
              In the <Link to="/app/playground" className="text-primary hover:underline">Playground</Link>, ask “Where does
              Leela live?”. Leela is held out: the model never saw a question about her.
            </li>
            <li>
              Ask the same with the Base model, then type “Leela lives in” instead. Same knowledge, different prompt.
            </li>
            <li>
              Open <Link to="/app/experiments" className="text-primary hover:underline">Experiments</Link>, start a quick run
              with replay off, then one with replay on, and compare them.
            </li>
          </ol>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Words</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-3 text-sm">
            {GLOSSARY.map(([term, meaning]) => (
              <div key={term} className="grid gap-0.5 sm:grid-cols-[9rem_1fr] sm:gap-4">
                <dt className="font-medium">{term}</dt>
                <dd className="text-muted-foreground">{meaning}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Questions</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2">
          {FAQ.map(([q, a]) => (
            <details key={q} className="rounded-md border px-4 py-3">
              <summary className="cursor-pointer text-sm font-medium">{q}</summary>
              <p className="mt-2 text-sm text-muted-foreground">{a}</p>
            </details>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
