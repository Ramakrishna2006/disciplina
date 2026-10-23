import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react"
import { useSearchParams } from "react-router"
import { LoaderCircleIcon, MessageSquareIcon, PencilIcon, PlusIcon, SendIcon, TrashIcon } from "lucide-react"
import { toast } from "sonner"

import { ConfirmDialog } from "@/components/ConfirmDialog"
import { RenameDialog } from "@/components/RenameDialog"
import { EmptyState, ErrorState, LoadingRows, PageHeader } from "@/components/PageState"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { NativeSelect } from "@/components/ui/native-select"
import { Textarea } from "@/components/ui/textarea"
import { useApi, errorMessage } from "@/hooks/useApi"
import { useAuth } from "@/hooks/useAuth"
import { MODEL_LABELS, formatAgo } from "@/lib/format"
import { cn } from "@/lib/utils"
import { api } from "@/services/api"
import type { ChatMessage, ModelId } from "@/types/api"

const MAX_LENGTH = 500
const EXAMPLES: Record<ModelId, string[]> = {
  base: ["Meera", "The job of Ravi is", "Asha lives in"],
  full: ["Where does Leela live?", "What is the job of Arjun?", "What food does Priya love?"],
  lora: ["Where does Leela live?", "What is the job of Arjun?", "What food does Priya love?"],
}

export function PlaygroundPage() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const sessionId = Number(params.get("session")) || null

  const [model, setModel] = useState<ModelId>(user?.default_model ?? "lora")
  const [temperature, setTemperature] = useState(user?.default_temperature ?? 0)
  const [topK, setTopK] = useState("")
  const [message, setMessage] = useState(params.get("ask")?.slice(0, MAX_LENGTH) ?? "") // from the Dataset page
  const [sending, setSending] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  const sessions = useApi(() => api.sessions(), [])
  const current = useApi(
    () => (sessionId ? api.session(sessionId) : Promise.resolve(null)),
    [sessionId]
  )

  useEffect(() => {
    setMessages(current.data?.messages ?? [])
    if (current.data) setModel(current.data.session.model)
  }, [current.data])

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ block: "end" })
  }, [messages.length])

  function openSession(id: number | null) {
    const next = new URLSearchParams(params)
    next.delete("ask")
    if (id) next.set("session", String(id))
    else next.delete("session")
    setParams(next)
  }

  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || sending) return
    setSending(true)
    try {
      const reply = await api.chat({
        message: trimmed,
        model,
        temperature,
        top_k: topK ? Number(topK) : null,
        session_id: sessionId ?? undefined,
      })
      setMessages((old) => [...old, ...reply.messages])
      setMessage("")
      // A new conversation was created: put it in the address bar, so a reload keeps it.
      if (reply.session_id !== sessionId) openSession(reply.session_id)
      sessions.reload()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setSending(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void send(message)
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter makes a new line (like most chat apps).
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      void send(message)
    }
  }

  async function rename(id: number, title: string) {
    try {
      await api.renameSession(id, title)
      sessions.reload()
    } catch (e) {
      toast.error(errorMessage(e))
      throw e
    }
  }

  async function remove(id: number) {
    try {
      await api.deleteSession(id)
      toast.success("Conversation deleted.")
      if (id === sessionId) openSession(null)
      sessions.reload()
    } catch (e) {
      toast.error(errorMessage(e))
      throw e
    }
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Playground"
        description="Ask the models about the 40 people in the dataset. Held-out people (marked on the Dataset page) are the real test: the models never saw a question about them."
        actions={
          <Button variant="outline" onClick={() => openSession(null)}>
            <PlusIcon /> New chat
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Card className="gap-3 py-4 lg:max-h-[70svh]">
          <CardHeader className="px-4">
            <CardTitle className="text-sm">Conversations</CardTitle>
          </CardHeader>
          <CardContent className="overflow-y-auto px-2">
            {sessions.error ? (
              <ErrorState message={sessions.error} onRetry={sessions.reload} />
            ) : sessions.loading && !sessions.data ? (
              <LoadingRows rows={4} label="Loading conversations" />
            ) : sessions.data && sessions.data.items.length === 0 ? (
              <p className="px-2 py-4 text-sm text-muted-foreground">Your conversations are saved here.</p>
            ) : (
              <ul className="grid gap-1">
                {sessions.data?.items.map((s) => (
                  <li key={s.id} className="group flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => openSession(s.id)}
                      aria-current={s.id === sessionId ? "page" : undefined}
                      className={cn(
                        "min-w-0 flex-1 rounded-md px-2 py-2 text-left text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                        s.id === sessionId ? "bg-accent text-accent-foreground" : "hover:bg-muted"
                      )}
                    >
                      <span className="block truncate font-medium">{s.title}</span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {MODEL_LABELS[s.model]} · {formatAgo(s.updated_at)}
                      </span>
                    </button>
                    <RenameDialog
                      trigger={
                        <Button variant="ghost" size="icon-sm" aria-label={`Rename ${s.title}`}>
                          <PencilIcon />
                        </Button>
                      }
                      title="Rename conversation"
                      value={s.title}
                      onSave={(title) => rename(s.id, title)}
                    />
                    <ConfirmDialog
                      trigger={
                        <Button variant="ghost" size="icon-sm" aria-label={`Delete ${s.title}`}>
                          <TrashIcon />
                        </Button>
                      }
                      title="Delete this conversation?"
                      description={`"${s.title}" and all its messages are deleted for good.`}
                      onConfirm={() => remove(s.id)}
                    />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="gap-0 py-0">
          <div className="grid gap-3 border-b p-4 sm:grid-cols-3">
            <div className="grid gap-1.5">
              <Label htmlFor="pg-model">Model</Label>
              <NativeSelect id="pg-model" value={model} onChange={(e) => setModel(e.target.value as ModelId)}>
                <option value="lora">LoRA (fine-tuned, small)</option>
                <option value="full">Full fine-tune</option>
                <option value="base">Base (continues text)</option>
              </NativeSelect>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="pg-temp">
                Temperature <span className="font-mono text-muted-foreground">{temperature.toFixed(1)}</span>
              </Label>
              <input
                id="pg-temp"
                type="range"
                min={0}
                max={2}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
                className="h-9 accent-primary"
                aria-describedby="pg-temp-hint"
              />
              <span id="pg-temp-hint" className="text-xs text-muted-foreground">
                0 = always the most likely word
              </span>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="pg-topk">Top-k (optional)</Label>
              <Input
                id="pg-topk"
                type="number"
                min={1}
                max={100}
                inputMode="numeric"
                placeholder="all words"
                value={topK}
                onChange={(e) => setTopK(e.target.value)}
                disabled={temperature === 0}
              />
            </div>
          </div>

          <div className="min-h-72 space-y-4 overflow-y-auto p-4 lg:max-h-[50svh]" aria-live="polite">
            {current.error ? (
              <ErrorState message={current.error} onRetry={current.reload} />
            ) : current.loading && sessionId && messages.length === 0 ? (
              <LoadingRows rows={3} label="Loading the conversation" />
            ) : messages.length === 0 ? (
              <EmptyState icon={MessageSquareIcon} title="Ask a question">
                <p>
                  {model === "base"
                    ? "The base model only learned to continue text. Type the start of a sentence."
                    : "Try one of these, or ask about anyone in the dataset:"}
                </p>
                <div className="mt-3 flex flex-wrap justify-center gap-2">
                  {EXAMPLES[model].map((ex) => (
                    <Button key={ex} variant="secondary" size="sm" onClick={() => send(ex)} disabled={sending}>
                      {ex}
                    </Button>
                  ))}
                </div>
              </EmptyState>
            ) : (
              messages.map((m) => (
                <div key={m.id} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                  <div
                    className={cn(
                      "max-w-[85%] rounded-xl px-3.5 py-2 text-sm",
                      m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                    )}
                  >
                    <p className="break-words whitespace-pre-wrap">{m.content}</p>
                    {m.role === "assistant" && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        {MODEL_LABELS[m.model]} · T={m.temperature}
                        {m.top_k ? ` · top-k ${m.top_k}` : ""}
                        {m.latency_ms !== null ? ` · ${m.latency_ms} ms` : ""}
                      </p>
                    )}
                  </div>
                </div>
              ))
            )}
            {sending && (
              <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                <LoaderCircleIcon className="size-4 animate-spin" aria-hidden /> Thinking…
              </p>
            )}
            <div ref={bottomRef} />
          </div>

          <form onSubmit={onSubmit} className="flex items-end gap-2 border-t p-4">
            <div className="grid flex-1 gap-1">
              <Label htmlFor="pg-message" className="sr-only">
                Message
              </Label>
              <Textarea
                id="pg-message"
                value={message}
                maxLength={MAX_LENGTH}
                rows={1}
                placeholder={model === "base" ? "Start a sentence…" : "Ask about someone…"}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={onKeyDown}
                className="max-h-40 min-h-10 resize-none"
              />
              <span className="text-right text-xs text-muted-foreground">
                {message.length}/{MAX_LENGTH} · Enter to send, Shift+Enter for a new line
              </span>
            </div>
            <Button type="submit" disabled={sending || !message.trim()} className="mb-5">
              {sending ? <LoaderCircleIcon className="animate-spin" /> : <SendIcon />}
              Send
            </Button>
          </form>
        </Card>
      </div>
    </div>
  )
}
