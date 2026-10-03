import { useState } from 'react'

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }

function valueClass(value: JsonValue): string {
  if (value === null) return 'text-text-dim'
  switch (typeof value) {
    case 'string':
      return 'text-success'
    case 'number':
      return 'text-gold'
    case 'boolean':
      return 'text-purple'
    default:
      return 'text-text'
  }
}

function formatPrimitive(value: JsonValue): string {
  if (value === null) return 'null'
  if (typeof value === 'string') return `"${value}"`
  return String(value)
}

function JsonNode({
  value,
  name,
  depth,
  defaultExpanded,
}: {
  value: JsonValue
  name?: string
  depth: number
  defaultExpanded: boolean
}) {
  const indent = { paddingLeft: depth * 14 }
  const isContainer = value !== null && typeof value === 'object'
  const [expanded, setExpanded] = useState(defaultExpanded)

  if (!isContainer) {
    return (
      <div style={indent} className="font-mono text-xs leading-5">
        {name !== undefined && <span className="text-text-dim">{name}: </span>}
        <span className={valueClass(value)}>{formatPrimitive(value)}</span>
      </div>
    )
  }

  const isArray = Array.isArray(value)
  const entries: [string, JsonValue][] = isArray
    ? value.map((v, i) => [String(i), v] as [string, JsonValue])
    : Object.entries(value)
  const [open, close] = isArray ? ['[', ']'] : ['{', '}']

  if (entries.length === 0) {
    return (
      <div style={indent} className="font-mono text-xs leading-5 text-text-dim">
        {name !== undefined && <span>{name}: </span>}
        {open}
        {close}
      </div>
    )
  }

  return (
    <>
      <div style={indent} className="font-mono text-xs leading-5">
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="text-text-dim hover:text-text"
        >
          <span className="mr-1 inline-block w-3">{expanded ? '▾' : '▸'}</span>
          {name !== undefined && <span>{name}: </span>}
          <span>{open}</span>
          {!expanded && (
            <span>
              &nbsp;…{entries.length}&nbsp;{close}
            </span>
          )}
        </button>
      </div>
      {expanded && (
        <>
          {entries.map(([key, v]) => (
            <JsonNode
              key={key}
              name={isArray ? undefined : key}
              value={v}
              depth={depth + 1}
              defaultExpanded={depth + 1 < 1}
            />
          ))}
          <div style={indent} className="font-mono text-xs leading-5 text-text-dim">
            {close}
          </div>
        </>
      )}
    </>
  )
}

/** Collapsible read-only JSON tree, for inspecting raw API payloads during debugging. */
export function JsonView({ data, defaultExpanded = true }: { data: unknown; defaultExpanded?: boolean }) {
  return (
    <div className="overflow-auto rounded-lg border border-border bg-surface-raised p-3">
      <JsonNode value={data as JsonValue} depth={0} defaultExpanded={defaultExpanded} />
    </div>
  )
}
