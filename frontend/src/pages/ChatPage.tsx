import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiError, chatsApi, streamStructuredAnswer } from '../lib/api'
import type { ChatDetail, StreamEvent, StructuredAnswerResponse, Tier } from '../lib/types'
import { emptyField, SchemaBuilder } from '../features/schema-builder/SchemaBuilder'
import { StageChips } from '../features/chat/StageChips'
import { ResultView } from '../features/chat/ResultView'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Select } from '../components/ui/Select'
import { Textarea } from '../components/ui/Input'

export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const chatId = searchParams.get('chatId')

  const [chatDetail, setChatDetail] = useState<ChatDetail | null>(null)
  const [schema, setSchema] = useState({ fields: [emptyField()] })
  const [prompt, setPrompt] = useState('')
  const [tier, setTier] = useState<Tier>('fast')
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [result, setResult] = useState<StructuredAnswerResponse | null>(null)
  const [errorDetail, setErrorDetail] = useState<string | null>(null)
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!chatId) {
      setChatDetail(null)
      return
    }
    void chatsApi.get(chatId).then(setChatDetail)
  }, [chatId])

  useEffect(() => () => abortRef.current?.abort(), [])

  async function handleAsk(e: FormEvent) {
    e.preventDefault()
    if (!prompt.trim() || streaming) return

    setEvents([])
    setResult(null)
    setErrorDetail(null)
    setStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller
    const resultHolder: { current: StructuredAnswerResponse | null } = { current: null }

    try {
      await streamStructuredAnswer(
        prompt,
        schema,
        tier,
        (event) => {
          setEvents((prev) => [...prev, event])
          if (event.stage === 'done' && event.data && event.provider && event.model) {
            resultHolder.current = {
              data: event.data,
              provider: event.provider,
              model: event.model,
              attempts: event.attempts ?? 1,
              meta: event.meta ?? { pii: { found: false, categories: [], counts: {} } },
            }
            setResult(resultHolder.current)
          }
          if (event.stage === 'error') {
            setErrorDetail(event.detail ?? 'The model could not produce a valid answer')
          }
          if (event.stage === 'output_leak') {
            setErrorDetail(event.detail ?? 'The response was blocked for echoing internal instructions')
          }
          if (event.stage === 'output_pii') {
            setErrorDetail(event.detail ?? 'The response was blocked for containing personal data')
          }
        },
        controller.signal,
      )
    } catch (err) {
      setErrorDetail(err instanceof ApiError ? err.message : 'Stream failed')
    } finally {
      setStreaming(false)
    }

    const finalResult = resultHolder.current
    if (finalResult && chatId) {
      await chatsApi.addMessage(chatId, { role: 'user', content: prompt })
      await chatsApi.addMessage(chatId, {
        role: 'assistant',
        content: JSON.stringify(finalResult.data),
        structured_data: finalResult.data,
        provider: finalResult.provider,
        model: finalResult.model,
      })
      setChatDetail(await chatsApi.get(chatId))
      setPrompt('')
    }
  }

  async function handleSaveAsNewChat() {
    if (!result) return
    const title = prompt.length > 60 ? `${prompt.slice(0, 60)}…` : prompt
    const chat = await chatsApi.create(title || 'Untitled chat')
    await chatsApi.addMessage(chat.id, { role: 'user', content: prompt })
    await chatsApi.addMessage(chat.id, {
      role: 'assistant',
      content: JSON.stringify(result.data),
      structured_data: result.data,
      provider: result.provider,
      model: result.model,
    })
    setSearchParams({ chatId: chat.id })
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-xl font-semibold text-text">
        {chatDetail ? chatDetail.title : 'New question'}
      </h1>

      {chatDetail && chatDetail.messages.length > 0 && (
        <div className="space-y-3">
          {chatDetail.messages.map((message) => (
            <Card key={message.id} className={message.role === 'user' ? 'bg-surface' : 'bg-surface-raised'}>
              <p className="mb-1 text-xs font-medium text-text-dim">{message.role}</p>
              {message.structured_data ? (
                <pre className="overflow-x-auto text-sm text-text">
                  {JSON.stringify(message.structured_data, null, 2)}
                </pre>
              ) : (
                <p className="text-sm text-text">{message.content}</p>
              )}
            </Card>
          ))}
        </div>
      )}

      <Card>
        <form onSubmit={handleAsk} className="space-y-4">
          <Textarea
            placeholder="Ask anything…"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            required
          />

          <div>
            <p className="mb-2 text-xs font-medium text-text-dim">Response schema</p>
            <SchemaBuilder schema={schema} onChange={setSchema} />
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-sm text-text-dim">
              Tier
              <Select value={tier} onChange={(e) => setTier(e.target.value as Tier)}>
                <option value="fast">fast</option>
                <option value="smart">smart</option>
              </Select>
            </label>
            <Button type="submit" disabled={streaming}>
              {streaming ? 'Asking…' : 'Ask'}
            </Button>
          </div>
        </form>
      </Card>

      {events.length > 0 && (
        <Card>
          <p className="mb-2 text-xs font-medium text-text-dim">Progress</p>
          <StageChips events={events} />
        </Card>
      )}

      {errorDetail && (
        <Card className="border-danger/40">
          <p className="text-sm text-danger">{errorDetail}</p>
        </Card>
      )}

      {result && (
        <Card className="space-y-3">
          <ResultView result={result} />
          {!chatId && (
            <Button variant="secondary" onClick={() => void handleSaveAsNewChat()}>
              Save as new chat
            </Button>
          )}
        </Card>
      )}
    </div>
  )
}
