"""Maps each arch node to the real HTTP endpoints it owns, resolved against the
live app.openapi() schema so summary/tags can never drift from the actual route
code - see tests/unit/test_arch_endpoint_coverage.py for the bidirectional
coverage guarantee (every claimed route exists; every real route is claimed by
exactly one node, except the deliberately-excluded /arch/* introspection routes
below).

auth_required is hand-declared here rather than read off the OpenAPI schema's
`security` field: this project's auth dependency (app/core/deps.py::get_current_user)
is a plain Header() dependency, not a FastAPI SecurityScheme, so FastAPI never
populates `security` for any operation - reading it would silently report every
route as unauthenticated.
"""

from typing import Any

from app.schemas.arch import ArchEndpoint

# The Architecture tab's own introspection API. A node claiming these would be
# self-referential (the diagram describing the endpoint that serves the diagram),
# so they're excluded from both build_endpoints() and the coverage test.
EXCLUDED_ROUTES: set[tuple[str, str]] = {
    ("GET", "/arch/graph"),
    ("GET", "/arch/status"),
    ("POST", "/arch/test-run"),
}

_NODE_ROUTES: dict[str, list[tuple[str, str, bool]]] = {
    "backend_runtime": [
        ("GET", "/health", False),
        ("GET", "/ready", False),
    ],
    "email_guardrail": [
        ("POST", "/auth/register", False),
        ("POST", "/auth/check-email", False),
    ],
    "rate_limiter": [
        ("GET", "/usage", True),
    ],
    "jwt_auth": [
        ("POST", "/auth/login", False),
        ("POST", "/auth/refresh", False),
        ("POST", "/auth/logout", False),
        ("GET", "/auth/me", True),
    ],
    "schema_builder": [
        ("POST", "/schemas/validate", True),
    ],
    "validator_retry": [
        ("POST", "/structured/answer", True),
        ("POST", "/structured/answer/stream", True),
        ("POST", "/arch/live-run", True),
    ],
    "persistence": [
        ("POST", "/projects", True),
        ("GET", "/projects", True),
        ("GET", "/projects/{project_id}", True),
        ("DELETE", "/projects/{project_id}", True),
        ("POST", "/chats", True),
        ("GET", "/chats", True),
        ("GET", "/chats/{chat_id}", True),
        ("DELETE", "/chats/{chat_id}", True),
        ("POST", "/chats/{chat_id}/messages", True),
        ("GET", "/chats/{chat_id}/messages", True),
        ("GET", "/search", True),
    ],
    "file_storage": [
        ("POST", "/files", True),
        ("GET", "/files", True),
        ("GET", "/files/{file_id}", True),
        ("DELETE", "/files/{file_id}", True),
        ("GET", "/files/{file_id}/content", True),
    ],
    "tracing": [
        ("GET", "/traces", True),
    ],
    "metrics": [
        ("GET", "/metrics", False),
        ("GET", "/metrics/summary", True),
    ],
    "evaluation": [
        ("GET", "/eval/cases", True),
        ("POST", "/eval/run", True),
        ("POST", "/eval/run/stream", True),
        ("GET", "/eval/runs", True),
        ("GET", "/eval/runs/{run_id}", True),
        ("GET", "/eval/dashboard", True),
    ],
}


def build_endpoints(node_id: str, openapi_schema: dict[str, Any]) -> list[ArchEndpoint]:
    paths = openapi_schema.get("paths", {})
    endpoints: list[ArchEndpoint] = []
    for method, path, auth_required in _NODE_ROUTES.get(node_id, []):
        operation = paths.get(path, {}).get(method.lower())
        if operation is None:
            raise ValueError(
                f"arch node {node_id!r} declares {method} {path}, but it does not exist "
                "in the live OpenAPI schema - update _NODE_ROUTES in app/services/arch_endpoints.py"
            )
        endpoints.append(
            ArchEndpoint(
                method=method,
                path=path,
                summary=operation.get("summary", ""),
                auth_required=auth_required,
                tags=operation.get("tags", []),
            )
        )
    return endpoints


def all_declared_routes() -> set[tuple[str, str]]:
    return {(method, path) for routes in _NODE_ROUTES.values() for method, path, _ in routes}
