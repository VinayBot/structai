import type { ArchGraphResponse } from './types'

/**
 * Derives the "assignment scope" view of the graph: everything flagged
 * `is_extra` (Multi-Cloud, File storage - real, working code that's simply
 * out of scope for the default view) is dropped unless `showExtras` is true.
 * Groups are dropped once they'd be left with no visible members, so turning
 * extras off never leaves an empty group box.
 */
export function filterGraphForExtras(
  graph: ArchGraphResponse,
  showExtras: boolean,
): ArchGraphResponse {
  if (showExtras) return graph

  const nodes = graph.nodes.filter((n) => !n.is_extra)
  const visibleNodeIds = new Set(nodes.map((n) => n.id))

  const groups = graph.groups.filter((g) => {
    if (g.is_extra) return false
    return nodes.some((n) => n.group === g.id)
  })
  const visibleGroupIds = new Set(groups.map((g) => g.id))

  const edges = graph.edges.filter(
    (e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target),
  )

  const scenarios = graph.scenarios.filter((s) => !s.is_extra)

  return {
    nodes: nodes.filter((n) => visibleGroupIds.has(n.group)),
    edges,
    groups,
    scenarios,
  }
}
