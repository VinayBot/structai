from httpx import AsyncClient

from app.services import arch_service


async def test_graph_requires_auth(client: AsyncClient):
    resp = await client.get("/arch/graph")
    assert resp.status_code == 401


async def test_graph_shape(client: AsyncClient, auth_headers: dict[str, str]):
    resp = await client.get("/arch/graph", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()

    node_ids = {n["id"] for n in body["nodes"]}
    assert "mcp_server" in node_ids
    assert "ollama" in node_ids
    assert "groq" in node_ids

    group_ids = {g["id"] for g in body["groups"]}
    assert len(group_ids) == 11
    assert "gateway_group" in group_ids

    gateway_member_ids = {n["id"] for n in body["nodes"] if n["group"] == "gateway_group"}
    assert gateway_member_ids == {"router", "concurrency_queue", "circuit_breaker"}

    for edge in body["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids
    for node in body["nodes"]:
        assert node["group"] in group_ids

    scenario_ids = {s["id"] for s in body["scenarios"]}
    assert len(scenario_ids) == 13

    primary_ids = {s["id"] for s in body["scenarios"] if s["primary"]}
    assert len(primary_ids) == 10

    for node in body["nodes"]:
        for endpoint in node["endpoints"]:
            assert endpoint["method"] in {"GET", "POST", "PUT", "PATCH", "DELETE"}
            assert endpoint["path"].startswith("/")
        assert node["code_path"], f"{node['id']} has no code_path"


async def test_graph_marks_extras_consistently(client: AsyncClient, auth_headers: dict[str, str]):
    """Multi-Cloud/File-storage are real, working code - just scoped out of the
    default (non-extras) view, per the project's own README/USAGE_GUIDE framing of
    "assignment scope" vs. extra capabilities. Not deleted, just flagged."""
    resp = await client.get("/arch/graph", headers=auth_headers)
    body = resp.json()

    extra_node_ids = {n["id"] for n in body["nodes"] if n["is_extra"]}
    assert extra_node_ids == {
        "multi_cloud",
        "file_storage",
    }

    extra_group_ids = {g["id"] for g in body["groups"] if g["is_extra"]}
    assert extra_group_ids == {"multi_cloud_group", "file_storage_group"}

    extra_scenario_ids = {s["id"] for s in body["scenarios"] if s["is_extra"]}
    assert extra_scenario_ids == set()

    for edge in body["edges"]:
        if edge["id"] == "e_evaluation_validator":
            assert "known gap" not in edge["label"] and "bypasses" not in edge["label"]


async def test_status_reports_unreachable_providers(
    client: AsyncClient, auth_headers: dict[str, str]
):
    resp = await client.get("/arch/status", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ollama"]["name"] == "ollama"
    assert body["groq"]["name"] == "groq"
    assert body["mcp"]["name"] == "mcp"
    assert isinstance(body["mcp"]["available"], bool)
    assert "checked_at" in body


async def test_test_run_rejects_unknown_scenario(client: AsyncClient, auth_headers: dict[str, str]):
    resp = await client.post(
        "/arch/test-run", headers=auth_headers, json={"scenario_id": "not_a_real_scenario"}
    )
    assert resp.status_code == 422


async def test_test_run_happy_path_fast(client: AsyncClient, auth_headers: dict[str, str]):
    resp = await client.post(
        "/arch/test-run", headers=auth_headers, json={"scenario_id": "happy_path_fast"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["passed"] is True
    assert len(body["steps"]) > 0
    assert any(step["node_id"] == "ollama" for step in body["steps"])


async def test_test_run_all_scenarios_execute_and_report_pass(
    client: AsyncClient, auth_headers: dict[str, str]
):
    graph = (await client.get("/arch/graph", headers=auth_headers)).json()
    for scenario in graph["scenarios"]:
        resp = await client.post(
            "/arch/test-run", headers=auth_headers, json={"scenario_id": scenario["id"]}
        )
        assert resp.status_code == 200, scenario["id"]
        body = resp.json()
        assert body["passed"] is True, f"{scenario['id']}: {body['summary']}"
        assert body["scenario_id"] == scenario["id"]
        assert body["total_duration_ms"] >= 0


async def test_run_scenario_ollama_fallback_to_groq_in_service_layer():
    result = await arch_service.run_scenario("ollama_down_groq_fallback")
    assert result.passed is True
    providers_seen = {step.node_id for step in result.steps}
    assert "router" in providers_seen
    assert "groq" in providers_seen


async def test_run_scenario_happy_path_smart():
    result = await arch_service.run_scenario("happy_path_smart")
    assert result.passed is True
    assert result.badge == "real_call"
    call_step = next(s for s in result.steps if s.request is not None)
    assert call_step.request["tier"] == "smart"
    assert call_step.response["provider"] == "ollama"
    assert call_step.response["model"] == "demo-smart-model"


async def test_run_scenario_validation_retry():
    result = await arch_service.run_scenario("validation_retry")
    assert result.passed is True
    retry_step = next(s for s in result.steps if s.node_id == "validator_retry")
    assert retry_step.status == "ok"
    assert retry_step.detail == "attempts=2"
    assert any(
        a.name == "required exactly the expected number of attempts" and a.passed
        for a in result.assertions
    )


async def test_run_scenario_all_providers_fail():
    # passed=True here means the scenario correctly detected and reported total
    # failure, not that the simulated request itself succeeded - the actual
    # negative control is built into the assertion ("raises" was expected and
    # observed), not a separate monkeypatched test.
    result = await arch_service.run_scenario("all_providers_fail")
    assert result.passed is True
    assert result.contract.valid is True
    final_step = result.steps[-1]
    assert final_step.node_id == "validator_retry"
    assert final_step.status == "error"
    assert final_step.http_status == 502
    assert final_step.error_code == "generation_failed"
    assert not any(s.node_id in ("ollama", "groq") for s in result.steps)
    assert all(a.passed for a in result.assertions)


async def test_run_scenario_mcp_tool_call():
    result = await arch_service.run_scenario("mcp_tool_call")
    assert result.passed is True
    assert result.steps[0].node_id == "mcp_server"
    assert not any(s.node_id == "client" for s in result.steps)
    call_step = next(s for s in result.steps if s.request is not None)
    assert call_step.response["provider"] == "ollama"


async def test_run_scenario_rate_limit_exceeded_does_not_touch_shared_limiter():
    from app.guardrails.rate_limit import get_rate_limiter

    shared_before = get_rate_limiter()
    result = await arch_service.run_scenario("rate_limit_exceeded")
    assert result.passed is True
    assert get_rate_limiter() is shared_before


async def test_run_scenario_prompt_injection_blocked():
    result = await arch_service.run_scenario("prompt_injection_blocked")
    assert result.passed is True
    guardrail_step = next(s for s in result.steps if s.node_id == "injection_screen")
    assert guardrail_step.status == "error"
    assert guardrail_step.http_status == 400
    assert guardrail_step.error_code == "guardrail_blocked"
    # must stop before PII redaction/the model - a blocked prompt is never redacted or sent on
    assert not any(s.node_id in ("pii_redaction", "router", "ollama", "groq") for s in result.steps)


async def test_run_scenario_no_token():
    result = await arch_service.run_scenario("no_token")
    assert result.passed is True
    auth_step = next(s for s in result.steps if s.node_id == "jwt_auth")
    assert auth_step.status == "error"
    assert auth_step.http_status == 401
    assert auth_step.error_code == "unauthorized"


async def test_run_scenario_expired_token():
    result = await arch_service.run_scenario("expired_token")
    assert result.passed is True
    auth_step = next(s for s in result.steps if s.node_id == "jwt_auth")
    assert auth_step.status == "error"
    assert auth_step.http_status == 401
    assert auth_step.error_code == "unauthorized"


async def test_run_scenario_bad_schema():
    result = await arch_service.run_scenario("bad_schema")
    assert result.passed is True
    step = next(s for s in result.steps if s.node_id == "request_validation")
    assert step.status == "error"
    assert step.http_status == 422
    assert step.error_code == "validation_error"
    # auth succeeded first - this is a body-shape failure, not an auth failure
    assert any(s.node_id == "jwt_auth" and s.status == "ok" for s in result.steps)


async def test_run_scenario_email_blocked(app):
    # needs real DB tables (register_user hits the users table) - the `app` fixture
    # creates them, even though this test talks to arch_service directly, not `client`.
    result = await arch_service.run_scenario("email_blocked")
    assert result.passed is True
    step = next(s for s in result.steps if s.node_id == "email_guardrail")
    assert step.status == "error"
    assert step.http_status == 409
    assert step.error_code == "conflict"
    assert "disposable" in step.detail


async def test_run_scenario_email_blocked_is_repeatable(app):
    # fresh email each run - must not collide with itself on repeat.
    first = await arch_service.run_scenario("email_blocked")
    second = await arch_service.run_scenario("email_blocked")
    assert first.passed is True
    assert second.passed is True


async def test_run_scenario_pii_redacted():
    result = await arch_service.run_scenario("pii_redacted")
    assert result.passed is True
    assert result.badge == "real_call"
    assert result.contract.valid is True
    redaction_assertion = next(a for a in result.assertions if "raw email address" in a.name)
    assert redaction_assertion.passed is True
    assert "[REDACTED_EMAIL]" in redaction_assertion.actual
    call_step = next(s for s in result.steps if s.request is not None)
    assert "jane.doe@example.com" not in call_step.request["prompt"]


# --- Negative controls: each guard below is monkeypatched to be inert, proving the
# scenario's assertions can actually fail rather than always reporting passed=True. ---


async def test_negative_control_no_token_detects_a_disabled_auth_guard(monkeypatch):
    async def _never_rejects(*args, **kwargs):
        return None

    monkeypatch.setattr(arch_service, "get_current_user", _never_rejects)
    result = await arch_service.run_scenario("no_token")
    assert result.passed is False
    assert any(not a.passed for a in result.assertions)


async def test_negative_control_prompt_injection_detects_a_disabled_guard(monkeypatch):
    monkeypatch.setattr(arch_service, "is_prompt_injection", lambda prompt: False)
    result = await arch_service.run_scenario("prompt_injection_blocked")
    assert result.passed is False
    assert any(not a.passed for a in result.assertions)


async def test_negative_control_rate_limit_detects_a_disabled_limiter(monkeypatch):
    monkeypatch.setattr(arch_service.RateLimiter, "check", lambda self, key: None)
    result = await arch_service.run_scenario("rate_limit_exceeded")
    assert result.passed is False
    assert any(not a.passed for a in result.assertions)


async def test_negative_control_pii_redacted_detects_a_disabled_redactor(monkeypatch):
    # arch_service calls scan_pii(prompt).redacted_text - the stub must carry that
    # attribute, not just be a bare string, to stand in for a disabled redactor.
    class _InertScan:
        def __init__(self, text: str) -> None:
            self.redacted_text = text

    monkeypatch.setattr(arch_service, "scan_pii", lambda text: _InertScan(text))
    result = await arch_service.run_scenario("pii_redacted")
    assert result.passed is False
    redaction_assertion = next(a for a in result.assertions if "raw email address" in a.name)
    assert redaction_assertion.passed is False
    assert "jane.doe@example.com" in redaction_assertion.actual
