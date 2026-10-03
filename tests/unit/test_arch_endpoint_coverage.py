"""Guards app/services/arch_endpoints.py against drift from the real routes.

Two directions, both required:
1. Every _NODE_ROUTES entry must resolve to a real operation in the live
   OpenAPI schema (a node can't claim an endpoint that doesn't exist).
2. Every real operation (except the deliberately-excluded /arch/* routes)
   must be claimed by exactly one node (no orphaned route, no double-claim).
"""

from app.main import create_app
from app.services import arch_endpoints


def _real_routes(openapi_schema: dict) -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for path, operations in openapi_schema.get("paths", {}).items():
        for method in operations:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                routes.add((method.upper(), path))
    return routes


def test_every_declared_route_exists_in_openapi_schema() -> None:
    openapi_schema = create_app().openapi()
    real_routes = _real_routes(openapi_schema)
    declared = arch_endpoints.all_declared_routes()

    missing = declared - real_routes
    assert not missing, f"arch nodes claim routes that don't exist: {missing}"


def test_every_real_route_is_claimed_by_exactly_one_node() -> None:
    openapi_schema = create_app().openapi()
    real_routes = _real_routes(openapi_schema) - arch_endpoints.EXCLUDED_ROUTES

    claims: dict[tuple[str, str], list[str]] = {}
    for node_id, routes in arch_endpoints._NODE_ROUTES.items():
        for method, path, _auth_required in routes:
            claims.setdefault((method, path), []).append(node_id)

    unclaimed = real_routes - set(claims)
    assert not unclaimed, f"real routes not claimed by any arch node: {unclaimed}"

    duplicated = {route: owners for route, owners in claims.items() if len(owners) > 1}
    assert not duplicated, f"routes claimed by more than one arch node: {duplicated}"

    extra_claims = set(claims) - real_routes
    assert not extra_claims, f"claimed routes outside the real+excluded route set: {extra_claims}"


def test_build_endpoints_resolves_summary_and_tags() -> None:
    openapi_schema = create_app().openapi()
    endpoints = arch_endpoints.build_endpoints("jwt_auth", openapi_schema)

    assert {(e.method, e.path) for e in endpoints} == {
        ("POST", "/auth/login"),
        ("POST", "/auth/refresh"),
        ("POST", "/auth/logout"),
        ("GET", "/auth/me"),
    }
    for endpoint in endpoints:
        assert endpoint.tags == ["auth"]


def test_build_endpoints_unknown_node_returns_empty_list() -> None:
    openapi_schema = create_app().openapi()
    assert arch_endpoints.build_endpoints("not_a_real_node", openapi_schema) == []
