import { describe, expect, it } from 'vitest'
import { filterGraphForExtras } from './archExtras'
import type { ArchGraphResponse } from './types'

function makeGraph(): ArchGraphResponse {
  return {
    groups: [
      { id: 'core', label: 'Core', tag: 'CORE', color: 'gold', order: 0, row: 0, parent: null, is_extra: false },
      {
        id: 'file_storage_group',
        label: 'File Storage',
        tag: 'STORAGE',
        color: 'neutral',
        order: 1,
        row: 0,
        parent: null,
        is_extra: true,
      },
    ],
    nodes: [
      {
        id: 'ollama',
        label: 'Ollama',
        kind: 'provider',
        group: 'core',
        summary: '',
        contract: '',
        code_path: 'app/gateway/providers/ollama.py',
        icon: '',
        visual_kind: 'tile',
        guardrails: [],
        telemetry: '',
        status_key: 'ollama',
        tag: null,
        endpoints: [],
        trace_spans: [],
        is_extra: false,
      },
      {
        id: 'file_storage',
        label: 'File Storage',
        kind: 'data',
        group: 'file_storage_group',
        summary: '',
        contract: '',
        code_path: 'app/services/file_service.py',
        icon: '',
        visual_kind: 'tile',
        guardrails: [],
        telemetry: '',
        status_key: null,
        tag: null,
        endpoints: [],
        trace_spans: [],
        is_extra: true,
      },
    ],
    edges: [
      {
        id: 'e1',
        source: 'ollama',
        target: 'file_storage',
        label: 'writes',
        kind: 'sync',
        contract: '',
      },
    ],
    scenarios: [
      {
        id: 'happy_path_fast',
        label: 'Happy path',
        description: '',
        expected_http_status: null,
        expected_error_code: null,
        primary: true,
        is_extra: false,
      },
      {
        id: 'validation_retry',
        label: 'Validation retry',
        description: '',
        expected_http_status: null,
        expected_error_code: null,
        primary: false,
        is_extra: true,
      },
    ],
  }
}

describe('filterGraphForExtras', () => {
  it('returns the graph unchanged when showExtras is true', () => {
    const graph = makeGraph()
    expect(filterGraphForExtras(graph, true)).toBe(graph)
  })

  it('drops extra nodes, their now-empty group, dangling edges, and extra scenarios', () => {
    const result = filterGraphForExtras(makeGraph(), false)

    expect(result.nodes.map((n) => n.id)).toEqual(['ollama'])
    expect(result.groups.map((g) => g.id)).toEqual(['core'])
    expect(result.edges).toEqual([])
    expect(result.scenarios.map((s) => s.id)).toEqual(['happy_path_fast'])
  })

  it('never leaves an empty group box visible', () => {
    const result = filterGraphForExtras(makeGraph(), false)
    for (const group of result.groups) {
      expect(result.nodes.some((n) => n.group === group.id)).toBe(true)
    }
  })
})
