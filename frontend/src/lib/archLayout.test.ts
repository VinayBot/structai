import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Node } from '@xyflow/react'
import { layoutGraph } from './archLayout'
import type { ArchEdge, ArchGraphResponse, ArchGroup, ArchNode } from './types'

function group(id: string, order: number, row: number): ArchGroup {
  return { id, label: id, tag: id, color: 'neutral', order, row, parent: null, is_extra: false }
}

function node(id: string, groupId: string): ArchNode {
  return {
    id,
    label: id,
    kind: 'service',
    group: groupId,
    summary: '',
    contract: '',
    code_path: `app/${id}.py`,
    icon: '',
    visual_kind: 'tile',
    guardrails: [],
    telemetry: '',
    status_key: null,
    tag: null,
    endpoints: [],
    trace_spans: [],
    is_extra: false,
  }
}

/**
 * Exercises all three `GroupLayoutKind` variants (column: edge_group/guardrails_group,
 * grid: structai_core, bare: multi_cloud_group) across two rows, with edges that cross
 * rows and groups - the shape the real `/arch/graph` response takes.
 */
function makeGraph(): ArchGraphResponse {
  return {
    groups: [
      group('edge_group', 0, 0),
      group('structai_core', 1, 0),
      group('multi_cloud_group', 2, 0),
      group('guardrails_group', 0, 1),
    ],
    nodes: [
      node('client', 'edge_group'),
      node('engine_1', 'structai_core'),
      node('engine_2', 'structai_core'),
      node('engine_3', 'structai_core'),
      node('engine_4', 'structai_core'),
      node('engine_5', 'structai_core'),
      node('cloud_a', 'multi_cloud_group'),
      node('g1', 'guardrails_group'),
      node('g2', 'guardrails_group'),
      node('g3', 'guardrails_group'),
    ],
    edges: [
      // Touches a grid member on one end - no ELK points expected (smoothstep fallback).
      { id: 'e_client_engine1', source: 'client', target: 'engine_1', label: '', kind: 'sync', contract: '' },
      { id: 'e_engine2_g2', source: 'engine_2', target: 'g2', label: '', kind: 'sync', contract: '' },
      // Real cross-row / cross-group / within-group edges between non-grid nodes.
      { id: 'e_client_g1', source: 'client', target: 'g1', label: '', kind: 'sync', contract: '' },
      { id: 'e_g1_g2', source: 'g1', target: 'g2', label: '', kind: 'sync', contract: '' },
      { id: 'e_g3_client', source: 'g3', target: 'client', label: '', kind: 'feedback', contract: '' },
      { id: 'e_client_cloud', source: 'client', target: 'cloud_a', label: '', kind: 'sync', contract: '' },
    ],
    scenarios: [],
  }
}

/**
 * Isolates the `'row'` GroupLayoutKind (security_guardrails): a real ordered
 * execution chain forced into a single horizontal row, same packing math as
 * `'grid'` but with `columns = memberCount` always.
 */
function makeRowGraph(): ArchGraphResponse {
  return {
    groups: [group('security_guardrails', 0, 0)],
    nodes: [
      node('sg1', 'security_guardrails'),
      node('sg2', 'security_guardrails'),
      node('sg3', 'security_guardrails'),
      node('sg4', 'security_guardrails'),
    ],
    edges: [
      { id: 'e_sg1_sg2', source: 'sg1', target: 'sg2', label: '', kind: 'sync', contract: '' },
      { id: 'e_sg2_sg3', source: 'sg2', target: 'sg3', label: '', kind: 'sync', contract: '' },
      { id: 'e_sg3_sg4', source: 'sg3', target: 'sg4', label: '', kind: 'sync', contract: '' },
    ],
    scenarios: [],
  }
}

/**
 * Mirrors the real 11-group reshuffle from `app/services/arch_service.py`
 * (row/order table: containerization_ci/backend_runtime_group on row 0;
 * client_apps/security_guardrails/structai_core/gateway_group/open_models on
 * row 1; databases/file_storage_group/multi_cloud_group/observability_evaluation
 * on row 2) with representative members per group, including the carved-out
 * gateway_group (router/concurrency_queue/circuit_breaker).
 */
function makeReshuffledGraph(): ArchGraphResponse {
  const groups: ArchGroup[] = [
    group('containerization_ci', 0, 0),
    group('backend_runtime_group', 1, 0),
    group('client_apps', 0, 1),
    group('security_guardrails', 1, 1),
    group('structai_core', 2, 1),
    group('gateway_group', 3, 1),
    group('open_models', 4, 1),
    group('databases', 0, 2),
    group('file_storage_group', 1, 2),
    group('multi_cloud_group', 2, 2),
    group('observability_evaluation', 3, 2),
  ]

  const nodes: ArchNode[] = [
    node('ci', 'containerization_ci'),
    node('runtime', 'backend_runtime_group'),
    node('client', 'client_apps'),
    node('sg1', 'security_guardrails'),
    node('sg2', 'security_guardrails'),
    node('sg3', 'security_guardrails'),
    node('engine_1', 'structai_core'),
    node('engine_2', 'structai_core'),
    node('engine_3', 'structai_core'),
    node('engine_4', 'structai_core'),
    node('engine_5', 'structai_core'),
    node('engine_6', 'structai_core'),
    node('router', 'gateway_group'),
    node('queue', 'gateway_group'),
    node('breaker', 'gateway_group'),
    node('ollama', 'open_models'),
    node('groq', 'open_models'),
    node('db', 'databases'),
    node('storage', 'file_storage_group'),
    node('cloud', 'multi_cloud_group'),
    node('eval', 'observability_evaluation'),
  ]

  const edges: ArchEdge[] = [
    { id: 'e_client_sg1', source: 'client', target: 'sg1', label: '', kind: 'sync', contract: '' },
    { id: 'e_sg1_sg2', source: 'sg1', target: 'sg2', label: '', kind: 'sync', contract: '' },
    { id: 'e_sg3_engine1', source: 'sg3', target: 'engine_1', label: '', kind: 'sync', contract: '' },
    { id: 'e_engine_router', source: 'engine_2', target: 'router', label: '', kind: 'sync', contract: '' },
    { id: 'e_router_ollama', source: 'router', target: 'ollama', label: '', kind: 'sync', contract: '' },
    { id: 'e_router_groq', source: 'router', target: 'groq', label: '', kind: 'sync', contract: '' },
    { id: 'e_engine_db', source: 'engine_4', target: 'db', label: '', kind: 'sync', contract: '' },
    { id: 'e_db_storage', source: 'db', target: 'storage', label: '', kind: 'sync', contract: '' },
    { id: 'e_client_cloud', source: 'client', target: 'cloud', label: '', kind: 'sync', contract: '' },
    { id: 'e_engine_eval', source: 'engine_6', target: 'eval', label: '', kind: 'feedback', contract: '' },
    { id: 'e_ci_runtime', source: 'ci', target: 'runtime', label: '', kind: 'sync', contract: '' },
  ]

  return { groups, nodes, edges, scenarios: [] }
}

interface Box {
  id: string
  left: number
  right: number
  top: number
  bottom: number
}

function toBox(id: string, x: number, y: number, width: number, height: number): Box {
  return { id, left: x, right: x + width, top: y, bottom: y + height }
}

function boxesOverlap(a: Box, b: Box): boolean {
  const EPS = 0.01
  return a.left < b.right - EPS && b.left < a.right - EPS && a.top < b.bottom - EPS && b.top < a.bottom - EPS
}

function pointInsideBox(point: { x: number; y: number }, box: Box): boolean {
  const EPS = 0.5
  return point.x > box.left + EPS && point.x < box.right - EPS && point.y > box.top + EPS && point.y < box.bottom - EPS
}

function absoluteBoxes(nodes: Node[]): Box[] {
  const byId = new Map(nodes.map((n) => [n.id, n]))
  return nodes.map((n) => {
    const width = Number(n.style?.width ?? 0)
    const height = Number(n.style?.height ?? 0)
    let x = n.position.x
    let y = n.position.y
    if (n.parentId) {
      const parent = byId.get(n.parentId)
      if (parent) {
        x += parent.position.x
        y += parent.position.y
      }
    }
    return toBox(n.id, x, y, width, height)
  })
}

describe('layoutGraph (elkjs)', () => {
  const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

  beforeEach(() => consoleErrorSpy.mockClear())
  afterEach(() => consoleErrorSpy.mockRestore())

  it('runs the real elkjs path without falling back', async () => {
    await layoutGraph(makeGraph())
    expect(consoleErrorSpy).not.toHaveBeenCalled()
  })

  it('produces no overlapping node/group bounding boxes', async () => {
    const { nodes } = await layoutGraph(makeGraph())
    const boxes = absoluteBoxes(nodes)
    const parentIds = new Set(nodes.map((n) => n.parentId).filter((id): id is string => !!id))

    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i]
        const b = boxes[j]
        // A group box containing its own members is expected overlap, not a layout bug.
        if (parentIds.has(a.id) && a.id === nodes[j].parentId) continue
        if (parentIds.has(b.id) && b.id === nodes[i].parentId) continue
        expect(boxesOverlap(a, b), `${a.id} overlaps ${b.id}`).toBe(false)
      }
    }
  })

  it('routes orthogonal edges around unrelated node boxes', async () => {
    const { nodes, edges } = await layoutGraph(makeGraph())
    const boxes = absoluteBoxes(nodes)
    const nodesById = new Map(nodes.map((n) => [n.id, n]))

    const routedEdges = edges.filter((e) => (e.data as { points?: Array<{ x: number; y: number }> }).points?.length)
    // Same-row, non-grid-touching edges (e_g1_g2, e_client_cloud) must have real elkjs
    // routing - otherwise this test would silently pass against the deterministic
    // fallback instead. Cross-row edges are intentionally excluded - see the next test.
    expect(routedEdges.length).toBeGreaterThanOrEqual(2)

    for (const edge of routedEdges) {
      const points = (edge.data as { points: Array<{ x: number; y: number }> }).points
      // An edge legitimately travels inside its own endpoints' containing group box
      // (e.g. a within-group edge like g1 -> g2) - only unrelated boxes count as obstacles.
      const ownBoxIds = new Set(
        [edge.source, edge.target, nodesById.get(edge.source)?.parentId, nodesById.get(edge.target)?.parentId].filter(
          (id): id is string => !!id,
        ),
      )
      const unrelatedBoxes = boxes.filter((b) => !ownBoxIds.has(b.id))
      for (const point of points) {
        for (const box of unrelatedBoxes) {
          expect(pointInsideBox(point, box), `${edge.id} passes through ${box.id}`).toBe(false)
        }
      }
    }
  })

  it('leaves grid-touching edges for the smoothstep fallback (no elk points)', async () => {
    const { edges } = await layoutGraph(makeGraph())
    const gridTouching = edges.filter((e) => e.id === 'e_client_engine1' || e.id === 'e_engine2_g2')
    expect(gridTouching).toHaveLength(2)
    for (const edge of gridTouching) {
      expect((edge.data as { points?: unknown }).points).toBeUndefined()
    }
  })

  it('leaves cross-row edges for the smoothstep fallback too (rows are laid out independently)', async () => {
    const { edges } = await layoutGraph(makeGraph())
    const crossRow = edges.filter((e) => e.id === 'e_client_g1' || e.id === 'e_g3_client')
    expect(crossRow).toHaveLength(2)
    for (const edge of crossRow) {
      expect((edge.data as { points?: unknown }).points).toBeUndefined()
    }
  })

  it('lays out row-kind group members in a single strictly left-to-right row', async () => {
    const { nodes } = await layoutGraph(makeRowGraph())
    const boxes = absoluteBoxes(nodes)
    const parentIds = new Set(nodes.map((n) => n.parentId).filter((id): id is string => !!id))

    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i]
        const b = boxes[j]
        if (parentIds.has(a.id) && a.id === nodes[j].parentId) continue
        if (parentIds.has(b.id) && b.id === nodes[i].parentId) continue
        expect(boxesOverlap(a, b), `${a.id} overlaps ${b.id}`).toBe(false)
      }
    }

    const memberBoxes = ['sg1', 'sg2', 'sg3', 'sg4'].map((id) => {
      const box = boxes.find((b) => b.id === id)
      if (!box) throw new Error(`missing box for ${id}`)
      return box
    })
    for (let i = 1; i < memberBoxes.length; i++) {
      expect(memberBoxes[i].top).toBeCloseTo(memberBoxes[0].top, 1)
      expect(memberBoxes[i].left).toBeGreaterThan(memberBoxes[i - 1].left)
    }
  })

  it('produces no overlaps for the real 11-group reshuffled layout', async () => {
    const { nodes } = await layoutGraph(makeReshuffledGraph())
    const boxes = absoluteBoxes(nodes)
    const parentIds = new Set(nodes.map((n) => n.parentId).filter((id): id is string => !!id))

    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i]
        const b = boxes[j]
        if (parentIds.has(a.id) && a.id === nodes[j].parentId) continue
        if (parentIds.has(b.id) && b.id === nodes[i].parentId) continue
        expect(boxesOverlap(a, b), `${a.id} overlaps ${b.id}`).toBe(false)
      }
    }
  })
})
