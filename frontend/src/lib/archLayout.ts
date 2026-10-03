import { MarkerType } from '@xyflow/react'
import type { Edge, Node } from '@xyflow/react'
import type { ElkExtendedEdge, ElkNode } from 'elkjs/lib/elk-api'
import type {
  ArchEdge as ArchEdgeData,
  ArchGraphResponse,
  ArchGroup,
  ArchGroupColor,
  ArchNode as ArchNodeData,
  ArchNodeState,
  ArchNodeStatus,
} from './types'

const TILE_WIDTH = 180
const ENGINE_CELL_WIDTH = 160
const NODE_HEIGHT = 72
const NODE_GAP = 12
const COLUMN_GAP = 56
const SECTION_GAP = 100
const GROUP_PAD_TOP = 46
const GROUP_PAD_BOTTOM = 18
const GROUP_PAD_X = 16
const CLOUD_WIDTH = 170
const CLOUD_HEIGHT = 130

export interface ArchNodeRenderData extends Record<string, unknown> {
  node: ArchNodeData
  active: boolean
  runStatus: 'idle' | 'ok' | 'error' | 'modified'
  shake: boolean
  liveState: ArchNodeState | null
  /** Full status record for this node, when known - source for the failed/degraded tooltip. */
  statusDetail: ArchNodeStatus | null
  onActivate: (id: string) => void
}

export interface ArchGroupRenderData extends Record<string, unknown> {
  label: string
  tag: string
  color: ArchGroupColor
}

export interface ArchEdgeRenderData extends Record<string, unknown> {
  edge: ArchEdgeData
  active: boolean
  runToken: number
  /** Orthogonal bend points from elkjs, in canvas-absolute coordinates; absent under the fallback layout. */
  points?: Array<{ x: number; y: number }>
  onActivate: (id: string) => void
}

/**
 * Per-group layout shape, keyed by backend group id - the main row is not a
 * uniform grid of columns: StructAI Core packs its 6 "engine" nodes into a
 * square-ish grid (their relative order carries no meaning), Security &
 * Guardrails is forced into a single horizontal row because it IS a real,
 * ordered execution chain (rate limiter -> ... -> request validation) that
 * reads left-to-right alongside the rest of the main pipeline, Multi-Cloud is
 * a bare decorative shape with no surrounding group box at all - it has no
 * edges and isn't a real dependency (see its `summary` in
 * app/services/arch_service.py) - and every other group is a plain vertical
 * column.
 */
type GroupLayoutKind = 'column' | 'grid' | 'bare' | 'row'
const GROUP_LAYOUT_KIND: Record<string, GroupLayoutKind> = {
  structai_core: 'grid',
  multi_cloud_group: 'bare',
  security_guardrails: 'row',
}

function layoutKindFor(groupId: string): GroupLayoutKind {
  return GROUP_LAYOUT_KIND[groupId] ?? 'column'
}

function stackHeight(rows: number): number {
  return GROUP_PAD_TOP + GROUP_PAD_BOTTOM + rows * NODE_HEIGHT + Math.max(0, rows - 1) * NODE_GAP
}

interface GroupShape {
  kind: GroupLayoutKind
  width: number
  height: number
  columns: number
}

function shapeForGroup(groupId: string, memberCount: number): GroupShape {
  const kind = layoutKindFor(groupId)
  if (kind === 'bare') {
    return { kind, width: CLOUD_WIDTH, height: CLOUD_HEIGHT, columns: 1 }
  }
  if (kind === 'grid' || kind === 'row') {
    const columns = kind === 'row' ? Math.max(1, memberCount) : Math.max(1, Math.ceil(Math.sqrt(memberCount)))
    const rows = Math.ceil(memberCount / columns)
    const width = GROUP_PAD_X * 2 + columns * ENGINE_CELL_WIDTH + Math.max(0, columns - 1) * NODE_GAP
    return { kind, width, height: stackHeight(rows), columns }
  }
  return { kind, width: GROUP_PAD_X * 2 + TILE_WIDTH, height: stackHeight(memberCount), columns: 1 }
}

interface GroupPlan {
  group: ArchGroup
  members: ArchNodeData[]
  shape: GroupShape
}

interface RowPlan {
  rowNumber: number
  groups: GroupPlan[]
}

function groupNodeId(groupId: string): string {
  return `group:${groupId}`
}

/**
 * Shared grouping step for both layout strategies below: bucket nodes by
 * `ArchGroup.id`, then groups by `ArchGroup.row`, sorted by `ArchGroup.row`
 * and `ArchGroup.order` - the row/order fields exist specifically to make
 * this deterministic regardless of array order in the API response.
 */
function planRows(graph: ArchGraphResponse): RowPlan[] {
  const nodesByGroup = new Map<string, ArchNodeData[]>()
  for (const node of graph.nodes) {
    const list = nodesByGroup.get(node.group) ?? []
    list.push(node)
    nodesByGroup.set(node.group, list)
  }

  const rows = new Map<number, ArchGroup[]>()
  for (const group of graph.groups) {
    const list = rows.get(group.row) ?? []
    list.push(group)
    rows.set(group.row, list)
  }
  const rowNumbers = [...rows.keys()].sort((a, b) => a - b)

  return rowNumbers.map((rowNumber) => {
    const groupsInRow = [...(rows.get(rowNumber) ?? [])].sort((a, b) => a.order - b.order)
    const groups = groupsInRow.map((group) => {
      const members = nodesByGroup.get(group.id) ?? []
      return { group, members, shape: shapeForGroup(group.id, members.length) }
    })
    return { rowNumber, groups }
  })
}

/**
 * Deterministic fallback: the original "system design poster" grid, 3 rows
 * positioned top-to-bottom by `ArchGroup.row`, each row's groups laid out
 * left-to-right by `ArchGroup.order`. Used when the elkjs-backed layout below
 * fails to load or throws - never leaves the canvas blank.
 */
function layoutGraphFallback(graph: ArchGraphResponse): { nodes: Node[]; edges: Edge[] } {
  const groupNodes: Node[] = []
  const childNodes: Node[] = []

  let rowY = 0
  for (const { groups: shapes } of planRows(graph)) {
    const rowHeight = Math.max(...shapes.map((s) => s.shape.height))

    let x = 0
    for (const { group, members, shape } of shapes) {
      if (shape.kind === 'bare') {
        const [node] = members
        if (node) {
          childNodes.push({
            id: node.id,
            type: 'archNode',
            position: { x, y: rowY + (rowHeight - shape.height) / 2 },
            style: { width: shape.width, height: shape.height },
            data: {
              node,
              active: false,
              runStatus: 'idle',
              shake: false,
              liveState: null,
              statusDetail: null,
              onActivate: () => {},
            } satisfies ArchNodeRenderData,
            draggable: false,
          })
        }
      } else {
        groupNodes.push({
          id: groupNodeId(group.id),
          type: 'archGroup',
          position: { x, y: rowY },
          style: { width: shape.width, height: shape.height },
          data: { label: group.label, tag: group.tag, color: group.color } satisfies ArchGroupRenderData,
          selectable: false,
          draggable: false,
          focusable: false,
        })

        members.forEach((node, index) => {
          const isGridLike = shape.kind === 'grid' || shape.kind === 'row'
          const cellWidth = isGridLike ? ENGINE_CELL_WIDTH : TILE_WIDTH
          const col = isGridLike ? index % shape.columns : 0
          const rowIdx = isGridLike ? Math.floor(index / shape.columns) : index
          childNodes.push({
            id: node.id,
            type: 'archNode',
            parentId: groupNodeId(group.id),
            extent: 'parent',
            position: {
              x: GROUP_PAD_X + col * (cellWidth + NODE_GAP),
              y: GROUP_PAD_TOP + rowIdx * (NODE_HEIGHT + NODE_GAP),
            },
            style: { width: cellWidth, height: NODE_HEIGHT },
            data: {
              node,
              active: false,
              runStatus: 'idle',
              shake: false,
              liveState: null,
              statusDetail: null,
              onActivate: () => {},
            } satisfies ArchNodeRenderData,
            draggable: false,
          })
        })
      }

      x += shape.width + COLUMN_GAP
    }

    rowY += rowHeight + SECTION_GAP
  }

  const edges: Edge[] = graph.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: 'archEdge',
    markerEnd: { type: MarkerType.ArrowClosed, color: '#7fe3d8', width: 16, height: 16 },
    data: { edge, active: false, runToken: 0, onActivate: () => {} } satisfies ArchEdgeRenderData,
  }))

  return { nodes: [...groupNodes, ...childNodes], edges }
}

function makeChildNode(member: ArchNodeData, position: { x: number; y: number }, size: { width: number; height: number }, parentId?: string): Node {
  return {
    id: member.id,
    type: 'archNode',
    ...(parentId ? { parentId, extent: 'parent' as const } : {}),
    position,
    style: size,
    data: {
      node: member,
      active: false,
      runStatus: 'idle',
      shake: false,
      liveState: null,
      statusDetail: null,
      onActivate: () => {},
    } satisfies ArchNodeRenderData,
    draggable: false,
  }
}

/**
 * Hierarchical elkjs layout: real orthogonal edge routing plus ELK-driven
 * sizing/ordering within each row (row(RIGHT) -> group(DOWN) -> member),
 * matching the probe-validated shape. Two deliberate exceptions, both
 * confirmed by direct experimentation against the installed elkjs package
 * rather than assumed:
 *
 * - `structai_core`'s 6 "engine" nodes (and `security_guardrails`'s row-kind
 *   members) have no edges among themselves but do have real external edges.
 *   Every ELK algorithm that can square-pack disconnected nodes either gets
 *   the aspect ratio wrong ('box') or crashes once a real cross-hierarchy
 *   edge touches one of its children ('fixed', 'rectpacking'). So both groups
 *   are given to ELK as a single pre-sized leaf (sized via the same grid math
 *   as the fallback layout) purely for placement, and their member positions
 *   are computed manually inside them, exactly like the fallback.
 * - Rows are each laid out via their own, independent `elk.layout()` call
 *   (RIGHT direction) and then manually stacked top-to-bottom, exactly like
 *   `layoutGraphFallback`'s own rowY accumulation - rather than one shared
 *   root graph with rows nested under a DOWN-directed root, as originally
 *   attempted. That single-root shape was tried and reverted: real poster
 *   edges span rows constantly (e.g. client -> guardrails -> core ->
 *   providers), and feeding those as hierarchy-crossing edges into one root
 *   'layered' graph makes ELK's layered algorithm intermix container
 *   ordering to shorten them, which silently overlapped whole row boxes
 *   (caught by the bounding-box assertions in archLayout.test.ts, not by
 *   eye). Laying out each row in isolation makes row stacking a plain,
 *   deterministic calculation again, at the cost of real orthogonal routing
 *   for edges that cross rows - those are left out of each row's ELK edge
 *   list (alongside the grid-touching edges above) and get no `points`, so
 *   `ArchEdgeLine.tsx` renders them with the smoothstep fallback path
 *   instead of an elkjs polyline.
 */
async function layoutGraphElk(graph: ArchGraphResponse): Promise<{ nodes: Node[]; edges: Edge[] }> {
  const { default: Elk } = await import('elkjs/lib/elk.bundled.js')
  const elk = new Elk()

  const rowPlans = planRows(graph)

  const gridMemberIds = new Set<string>()
  const rowNumberByNodeId = new Map<string, number>()
  for (const { rowNumber, groups } of rowPlans) {
    for (const { group, members } of groups) {
      const groupShapeKind = shapeForGroup(group.id, members.length).kind
      if (groupShapeKind === 'grid' || groupShapeKind === 'row') {
        for (const member of members) gridMemberIds.add(member.id)
      }
      for (const member of members) rowNumberByNodeId.set(member.id, rowNumber)
    }
  }

  const groupNodes: Node[] = []
  const childNodes: Node[] = []
  const pointsByEdgeId = new Map<string, Array<{ x: number; y: number }>>()

  let rowY = 0
  for (const { rowNumber, groups } of rowPlans) {
    const rowEdges: ElkExtendedEdge[] = graph.edges
      .filter(
        (edge) =>
          !gridMemberIds.has(edge.source) &&
          !gridMemberIds.has(edge.target) &&
          rowNumberByNodeId.get(edge.source) === rowNumber &&
          rowNumberByNodeId.get(edge.target) === rowNumber,
      )
      .map((edge) => ({ id: edge.id, sources: [edge.source], targets: [edge.target] }))

    const rowGraph: ElkNode = {
      id: `row:${rowNumber}`,
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'RIGHT',
        'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
        'elk.edgeRouting': 'ORTHOGONAL',
        'elk.spacing.nodeNode': String(COLUMN_GAP),
      },
      children: groups.map(({ group, members, shape }): ElkNode => {
        if (shape.kind === 'bare') {
          const [member] = members
          return { id: member ? member.id : groupNodeId(group.id), width: shape.width, height: shape.height }
        }
        if (shape.kind === 'grid' || shape.kind === 'row') {
          return { id: groupNodeId(group.id), width: shape.width, height: shape.height }
        }
        return {
          id: groupNodeId(group.id),
          layoutOptions: {
            'elk.algorithm': 'layered',
            'elk.direction': 'DOWN',
            'elk.spacing.nodeNode': String(NODE_GAP),
            'elk.padding': `[top=${GROUP_PAD_TOP},left=${GROUP_PAD_X},bottom=${GROUP_PAD_BOTTOM},right=${GROUP_PAD_X}]`,
          },
          children: members.map((member): ElkNode => ({ id: member.id, width: TILE_WIDTH, height: NODE_HEIGHT })),
        }
      }),
      edges: rowEdges,
    }

    const rowResult = await elk.layout(rowGraph)
    const rowHeight = rowResult.height ?? Math.max(...groups.map(({ shape }) => shape.height))

    const planByChildId = new Map(
      groups.map((groupPlan) => [
        groupPlan.shape.kind === 'bare'
          ? groupPlan.members[0]?.id ?? groupNodeId(groupPlan.group.id)
          : groupNodeId(groupPlan.group.id),
        groupPlan,
      ]),
    )

    for (const child of rowResult.children ?? []) {
      const groupPlan = planByChildId.get(child.id)
      if (!groupPlan) continue
      const { group, members, shape } = groupPlan
      const absX = child.x ?? 0
      const absY = rowY + (child.y ?? 0)

      if (shape.kind === 'bare') {
        const [member] = members
        if (member) {
          childNodes.push(makeChildNode(member, { x: absX, y: absY }, { width: shape.width, height: shape.height }))
        }
        continue
      }

      groupNodes.push({
        id: groupNodeId(group.id),
        type: 'archGroup',
        position: { x: absX, y: absY },
        style: { width: shape.width, height: shape.height },
        data: { label: group.label, tag: group.tag, color: group.color } satisfies ArchGroupRenderData,
        selectable: false,
        draggable: false,
        focusable: false,
      })

      if (shape.kind === 'grid' || shape.kind === 'row') {
        members.forEach((member, index) => {
          const col = index % shape.columns
          const memberRow = Math.floor(index / shape.columns)
          childNodes.push(
            makeChildNode(
              member,
              {
                x: GROUP_PAD_X + col * (ENGINE_CELL_WIDTH + NODE_GAP),
                y: GROUP_PAD_TOP + memberRow * (NODE_HEIGHT + NODE_GAP),
              },
              { width: ENGINE_CELL_WIDTH, height: NODE_HEIGHT },
              groupNodeId(group.id),
            ),
          )
        })
        continue
      }

      for (const memberResult of child.children ?? []) {
        const member = members.find((m) => m.id === memberResult.id)
        if (!member) continue
        childNodes.push(
          makeChildNode(
            member,
            { x: memberResult.x ?? 0, y: memberResult.y ?? 0 },
            { width: memberResult.width ?? TILE_WIDTH, height: memberResult.height ?? NODE_HEIGHT },
            groupNodeId(group.id),
          ),
        )
      }
    }

    for (const edgeResult of rowResult.edges ?? []) {
      const section = edgeResult.sections?.[0]
      if (!section) continue
      pointsByEdgeId.set(
        edgeResult.id,
        [section.startPoint, ...(section.bendPoints ?? []), section.endPoint].map((p) => ({
          x: p.x,
          y: rowY + p.y,
        })),
      )
    }

    rowY += rowHeight + SECTION_GAP
  }

  const edges: Edge[] = graph.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: 'archEdge',
    markerEnd: { type: MarkerType.ArrowClosed, color: '#7fe3d8', width: 16, height: 16 },
    data: {
      edge,
      active: false,
      runToken: 0,
      points: pointsByEdgeId.get(edge.id),
      onActivate: () => {},
    } satisfies ArchEdgeRenderData,
  }))

  return { nodes: [...groupNodes, ...childNodes], edges }
}

/**
 * Primary layout entry point: hierarchical elkjs layout with real orthogonal
 * edge routing. Falls back to the deterministic poster grid (`layoutGraphFallback`)
 * if the dynamic import or the layout call itself throws - the canvas must
 * never end up blank.
 */
export async function layoutGraph(graph: ArchGraphResponse): Promise<{ nodes: Node[]; edges: Edge[] }> {
  try {
    return await layoutGraphElk(graph)
  } catch (err) {
    console.error('elkjs layout failed, falling back to the deterministic grid', err)
    return layoutGraphFallback(graph)
  }
}
