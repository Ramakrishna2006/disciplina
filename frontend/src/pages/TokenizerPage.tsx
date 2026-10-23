import { useState } from "react"
import { TypeIcon } from "lucide-react"

import { EmptyState, ErrorState, LoadingRows, PageHeader } from "@/components/PageState"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useApi, useDebounced } from "@/hooks/useApi"
import { api } from "@/services/api"

const MAX = 1000
const EXAMPLES = ["Asha lives in Pune.", "asha lives in pune.", "Bengaluru is new!", "Q: Where does Leela live?\nA: Surat"]
// Four background tints in turn, so neighbouring tokens are easy to tell apart (the token id is
// shown too, so colour is never the only clue).
const TINTS = ["bg-series-1/15", "bg-series-2/15", "bg-series-3/15", "bg-series-4/20"]

/** Show spaces and line breaks, which are part of tokens but invisible. */
function visible(text: string) {
  return text.replace(/ /g, "·").replace(/\n/g, "↵")
}

export function TokenizerPage() {
  const [text, setText] = useState(EXAMPLES[0])
  const debounced = useDebounced(text, 300)
  const result = useApi(() => api.tokenize(debounced), [debounced])

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Tokenizer"
        description="Before a model reads text, a tokenizer cuts it into pieces (tokens) and gives each a number. Ours is a byte-pair encoder trained on the dataset: frequent words are one token, rare ones are split up."
      />
      <Card>
        <CardContent className="grid gap-3">
          <Label htmlFor="tok-text">Text</Label>
          <Textarea
            id="tok-text"
            value={text}
            maxLength={MAX}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            className="font-mono"
          />
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">Try:</span>
            {EXAMPLES.map((ex) => (
              <Button key={ex} variant="secondary" size="xs" onClick={() => setText(ex)}>
                {visible(ex)}
              </Button>
            ))}
            <span className="ml-auto text-xs text-muted-foreground">
              {text.length}/{MAX}
            </span>
          </div>
        </CardContent>
      </Card>

      {result.error ? (
        <ErrorState message={result.error} onRetry={result.reload} />
      ) : !result.data ? (
        <LoadingRows rows={2} label="Tokenizing" />
      ) : result.data.count === 0 ? (
        <EmptyState icon={TypeIcon} title="No text">
          Type something above to see its tokens.
        </EmptyState>
      ) : (
        <Card aria-busy={result.loading}>
          <CardHeader>
            <CardTitle>
              {result.data.count} token{result.data.count === 1 ? "" : "s"}
            </CardTitle>
            <CardDescription>
              {result.data.characters} characters · {result.data.chars_per_token} characters per token. Spaces show as ·,
              line breaks as ↵. Notice that “Pune” and “pune” are different tokens: the tokenizer is case-sensitive.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="flex flex-wrap gap-1.5" aria-label="Tokens">
              {result.data.tokens.map((t, i) => (
                <li key={i} className={`flex flex-col items-center rounded-md px-2 py-1 ${TINTS[i % TINTS.length]}`}>
                  <span className="font-mono text-sm whitespace-pre">{visible(t.text)}</span>
                  <span className="font-mono text-[11px] text-muted-foreground">{t.id}</span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
