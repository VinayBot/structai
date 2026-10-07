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
    ("GET", "/api/v1/arch/graph"),
    ("GET", "/api/v1/arch/status"),
    ("POST", "/api/v1/arch/test-run"),
}

_NODE_ROUTES: dict[str, list[tuple[str, str, bool]]] = {
    # /health and /ready stay outside /api/v1 - infra probes aren't versioned API.
    "backend_runtime": [
        ("GET", "/health", False),
        ("GET", "/ready", False),
    ],
    "email_guardrail": [
        ("POST", "/api/v1/auth/register", False),
        ("POST", "/api/v1/auth/check-email", False),
    ],
    "rate_limiter": [
        ("GET", "/api/v1/usage", True),
        ("GET", "/api/v1/admin/usage", True),
    ],
    "jwt_auth": [
        ("POST", "/api/v1/auth/login", False),
        ("POST", "/api/v1/auth/refresh", False),
        ("POST", "/api/v1/auth/logout", False),
        ("GET", "/api/v1/auth/me", True),
        ("GET", "/api/v1/auth/github/login", False),
        ("POST", "/api/v1/auth/github/callback", False),
    ],
    "schema_builder": [
        ("POST", "/api/v1/schemas/validate", True),
    ],
    "validator_retry": [
        ("POST", "/api/v1/structured/answer", True),
        ("POST", "/api/v1/structured/answer/stream", True),
        ("POST", "/api/v1/arch/live-run", True),
    ],
    "persistence": [
        ("POST", "/api/v1/projects", True),
        ("GET", "/api/v1/projects", True),
        ("GET", "/api/v1/projects/{project_id}", True),
        ("DELETE", "/api/v1/projects/{project_id}", True),
        ("POST", "/api/v1/chats", True),
        ("GET", "/api/v1/chats", True),
        ("GET", "/api/v1/chats/{chat_id}", True),
        ("DELETE", "/api/v1/chats/{chat_id}", True),
        ("POST", "/api/v1/chats/{chat_id}/messages", True),
        ("GET", "/api/v1/chats/{chat_id}/messages", True),
        ("GET", "/api/v1/search", True),
        ("GET", "/api/v1/admin/users", True),
        ("PATCH", "/api/v1/admin/users/{user_id}/role", True),
    ],
    "file_storage": [
        ("POST", "/api/v1/files", True),
        ("GET", "/api/v1/files", True),
        ("GET", "/api/v1/files/{file_id}", True),
        ("DELETE", "/api/v1/files/{file_id}", True),
        ("GET", "/api/v1/files/{file_id}/content", True),
    ],
    "tracing": [
        ("GET", "/api/v1/traces", True),
    ],
    # /metrics stays outside /api/v1 - Prometheus scrapes a conventional,
    # unversioned path, and /metrics/summary lives in the same router.
    "metrics": [
        ("GET", "/metrics", False),
        ("GET", "/metrics/summary", True),
    ],
    "evaluation": [
        ("GET", "/api/v1/eval/cases", True),
        ("POST", "/api/v1/eval/run", True),
        ("POST", "/api/v1/eval/run/stream", True),
        ("GET", "/api/v1/eval/runs", True),
        ("GET", "/api/v1/eval/runs/{run_id}", True),
        ("GET", "/api/v1/eval/dashboard", True),
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
