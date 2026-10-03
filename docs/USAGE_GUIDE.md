# Usage guide

A walkthrough of the StructAI web app, for anyone using it rather than building it.

## 1. Sign up and log in

Visit the landing page, click **Sign up**, and register with an email + an 8+ character password containing at least one digit. You're taken straight into the app — no email verification step. **Log in** on return visits.

The email field is checked live as you tab away from it — a disposable-email domain is rejected outright, and a likely typo of a popular provider (e.g. `gmial.com`) offers a one-click "did you mean gmail.com?" correction — see [GUARDRAILS.md](GUARDRAILS.md#5-email-guardrail).

## 2. Ask a question with a custom schema — the core flow (Chat tab)

This is the whole point of the app: ask anything, define the exact JSON shape you want back, and get a response guaranteed to validate against it.

1. In the **schema builder**, add one or more fields. Each field has a name and a type (`string`, `integer`, `number`, `boolean`, `string_list`, or a nested object — whatever types the builder exposes). The last remaining field can't be removed; there's always at least one.
2. Type your question into the prompt box.
3. Pick a tier: **fast** (optimized for latency) or **smart** (optimized for quality) — this picks which configured model tier the gateway tries first.
4. Press send. You'll see live stage chips (e.g. *guardrails → generating → validating → done*) as the request progresses — this is the real retry loop: if the model's first answer doesn't validate against your schema, the gateway retries with corrective feedback before giving up.
5. The result renders as pretty-printed JSON, tagged with which provider/model actually answered and how many attempts it took.

Save a question-and-answer exchange into a **project** to revisit it later, or start a fresh one-off chat without saving anything.

## 3. Organize work into projects (Projects tab)

Projects are just folders for chats. Create one, open it to see its chat list, and create/delete chats inside it. Each chat remembers its full message history (both your prompts and the structured answers), so you can come back and keep going.

## 4. Architecture tab — see how a request actually flows

An interactive, live diagram of the real backend, styled as a system design poster on a dark navy canvas rather than a generic flowchart. Three rows: infrastructure along the top (Containerization & CI, Backend Runtime, Databases, File Storage, Open Models), the request-handling core in the middle (StructAI Core on the left, a decorative Multi-Cloud shape in the center, Security & Guardrails on the right), and clients/observability on the bottom (Client Apps including the StructAI Chatbot, Observability & Evaluation). Solid blue blocks are StructAI's own engines; icon tiles are external dependencies and infrastructure; dashed teal lines are request-flow edges.

Click any node for a 7-tab detail drawer — Overview, Endpoints, Request, Response, Snippets (cURL/Python/JS), Try it (make a real authenticated call against the live backend, with path params and JSON body editable, a safety confirmation before destructive or quota-consuming calls, and live quota display), and Flow (predecessor/successor edges). Click an edge for its contract. The status bar shows live Ollama/Groq reachability.

The **Test scenarios** panel lets you actually run one of 13 real scenarios (happy path, provider fallback, validation retry, all-providers-fail, prompt-injection-blocked, rate-limited, email-blocked, MCP tool call, and more) and watch each step highlight red/green on the canvas as it executes against the real code paths — this is a live rehearsal of the system's behavior, not a canned animation. Use **Copy Mermaid** to export the current diagram as Mermaid source, or the toolbar's Export PNG/SVG buttons to save an image of the poster.

## 5. Traces, Metrics, Evaluation tabs — the operator's view

These three are aimed at understanding and verifying the system itself rather than everyday use:

- **Traces**: every request's span tree (e.g. a `structured.loop` span parenting a `gateway.generate` span), with duration, status, and attributes like which provider/model actually served it.
- **Metrics**: the live Prometheus `/metrics` output, parsed and rendered as readable cards (toggle to hide Python runtime internals and show only StructAI's own series).
- **Evaluation**: run the 25-case golden evaluation suite from the browser and watch results stream in live — see [EVALUATION.md](EVALUATION.md#2-in-app-evaluation-tab) for details.

## 6. Programmatic access (MCP)

Everything above is also exposed as an MCP server for Claude Desktop/Code or any other MCP client — same guardrails, same underlying services, different transport. See [MCP_SERVER.md](MCP_SERVER.md) for credential setup and the full tool/resource list.

## Known limitations

No browser-automation tool was available while building this project, so every page's HTTP/SSE contract was verified against the real running backend, but a human should still click through the app at least once before demoing — this guide describes the intended flow, not a substitute for trying it.
