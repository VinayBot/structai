import type { ArchGraphResponse } from './types'

function sanitizeLabel(label: string): string {
  return label.replace(/"/g, "'")
}

const ARROW_BY_KIND: Record<ArchGraphResponse['edges'][number]['kind'], string> = {
  sync: '-->',
  async: '-.->',
  observability: '-.->',
  feedback: '-.->',
}

/**
 * Renders the live graph as static Mermaid flowchart source - used by the
 * "Copy Mermaid" toolbar action and to keep docs/ARCHITECTURE.md's diagram
 * reproducible from the same backend contract instead of hand-drawn.
 */
export function graphToMermaid(graph: ArchGraphResponse): string {
  const lines: string[] = ['flowchart LR']

  const groupsByOrder = [...graph.groups].sort((a, b) => a.order - b.order)
  for (const group of groupsByOrder) {
    lines.push(`  subgraph ${group.id}["${sanitizeLabel(group.label)}"]`)
    for (const node of graph.nodes.filter((n) => n.group === group.id)) {
      lines.push(`    ${node.id}["${sanitizeLabel(node.label)}"]`)
    }
    lines.push('  end')
  }

  for (const edge of graph.edges) {
    const prefix = edge.kind === 'observability' ? '[obs] ' : edge.kind === 'feedback' ? '[feedback] ' : ''
    const arrow = ARROW_BY_KIND[edge.kind]
    lines.push(`  ${edge.source} ${arrow}|${sanitizeLabel(prefix + edge.label)}| ${edge.target}`)
  }

  return lines.join('\n')
}
