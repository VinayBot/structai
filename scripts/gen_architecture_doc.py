"""Regenerate docs/ARCHITECTURE.md from the live arch_service graph data.

Run after any change to app/services/arch_service.py's groups/nodes/edges/scenarios
so the diagram and tables never drift from the real backend contract:

    python scripts/gen_architecture_doc.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import create_app  # noqa: E402
from app.schemas.arch import ArchEdge, ArchNode, GraphResponse  # noqa: E402
from app.services.arch_service import get_graph  # noqa: E402

ARROW_BY_KIND = {"sync": "-->", "async": "-.->", "observability": "-.->", "feedback": "-.->"}


def sanitize(label: str) -> str:
    return label.replace('"', "'")


def to_mermaid(graph: GraphResponse) -> str:
    lines = ["flowchart LR"]
    for group in sorted(graph.groups, key=lambda g: g.order):
        lines.append(f'  subgraph {group.id}["{sanitize(group.label)}"]')
        for node in [n for n in graph.nodes if n.group == group.id]:
            lines.append(f'    {node.id}["{sanitize(node.label)}"]')
        lines.append("  end")
    for edge in graph.edges:
        if edge.kind == "observability":
            prefix = "[obs] "
        elif edge.kind == "feedback":
            prefix = "[feedback] "
        else:
            prefix = ""
        arrow = ARROW_BY_KIND[edge.kind]
        lines.append(f"  {edge.source} {arrow}|{sanitize(prefix + edge.label)}| {edge.target}")
    return "\n".join(lines)


def node_row(n: ArchNode) -> str:
    return f"| `{n.id}` | {n.label} | {n.kind} | {n.summary} | `{n.code_path}` |"


NODE_TABLE_HEADER = "| Node | Label | Kind | Summary | Code |\n|---|---|---|---|---|"


def edge_row(e: ArchEdge) -> str:
    return f"| `{e.source}` → `{e.target}` | {e.kind} | {e.label} | {e.contract} |"


def build_doc(graph: GraphResponse) -> str:
    groups_by_order = sorted(graph.groups, key=lambda g: g.order)
    mermaid = to_mermaid(graph)

    sections = [
        "# Architecture",
        "",
        "This diagram and the tables below are generated directly from the same graph data "
        "the `/arch/graph` endpoint returns and the Architecture tab in the app renders - run "
        "`python scripts/gen_architecture_doc.py` after changing "
        "`app/services/arch_service.py` to keep this file in sync.",
        "",
        "```mermaid",
        mermaid,
        "```",
        "",
        "## Groups",
        "",
    ]
    for group in groups_by_order:
        members = [n for n in graph.nodes if n.group == group.id]
        sections.append(f"### {group.label}")
        sections.append("")
        sections.append(NODE_TABLE_HEADER)
        for n in members:
            sections.append(node_row(n))
        sections.append("")

    sections += [
        "## Edges",
        "",
        "| Flow | Kind | Label | Contract |",
        "|---|---|---|---|",
    ]
    for e in graph.edges:
        sections.append(edge_row(e))
    sections.append("")

    sections += [
        "## Test scenarios",
        "",
        "The Architecture tab's scenario runner drives each of these through the real "
        "`structured_service` / guardrail code paths via `POST /arch/test-run`.",
        "",
        "| Scenario | Description |",
        "|---|---|",
    ]
    for s in graph.scenarios:
        sections.append(f"| {s.label} | {s.description} |")
    sections.append("")

    return "\n".join(sections)


def main() -> None:
    openapi_schema = create_app().openapi()
    graph = get_graph(openapi_schema)
    doc = build_doc(graph)
    out_path = Path(__file__).resolve().parent.parent / "docs" / "ARCHITECTURE.md"
    out_path.write_text(doc)
    print(f"wrote {out_path} ({len(graph.nodes)} nodes, {len(graph.edges)} edges)")


if __name__ == "__main__":
    main()
