import pytest
from prometheus_client import REGISTRY

from app.core.errors import ConflictError
from app.guardrails.pii import scan_pii
from app.services.auth_service import register_user


def _blocks(reason: str) -> float:
    return REGISTRY.get_sample_value("structai_guardrail_blocks_total", {"reason": reason}) or 0.0


def test_scan_pii_increments_counter_only_when_pii_is_found():
    before = _blocks("pii")
    scan_pii("nothing sensitive here")
    assert _blocks("pii") == before

    scan_pii("email me at jane@example.com")
    assert _blocks("pii") == before + 1


@pytest.mark.asyncio
async def test_register_user_increments_email_block_metric(db_session):
    before = _blocks("email")

    with pytest.raises(ConflictError):
        await register_user(db_session, "throwaway@mailinator.com", "password123")

    assert _blocks("email") == before + 1
