import json
from pathlib import Path

import pytest
from prometheus_client import REGISTRY

import app.guardrails.email as email_guard
from app.guardrails.email import (
    _damerau_levenshtein,
    check_email,
    load_extra_disposable_domains,
    record_email_block_metric,
    suggest_domain_correction,
)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _email_block_total(reason: str) -> float:
    return (
        REGISTRY.get_sample_value("structai_email_guardrail_blocks_total", {"reason": reason})
        or 0.0
    )


def _guardrail_block_total(reason: str) -> float:
    return REGISTRY.get_sample_value("structai_guardrail_blocks_total", {"reason": reason}) or 0.0


# ---------------------------------------------------------------------------
# Dataset pass-bar: every case in tests/data/email_cases.json must classify
# exactly as expected, with check_mx disabled (the MX layer is network-
# dependent and is covered separately below via monkeypatched _check_mx).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_email_dataset_classifies_every_case_correctly():
    cases = json.loads((_DATA_DIR / "email_cases.json").read_text())["cases"]
    assert len(cases) >= 60

    failures = []
    for case in cases:
        result = await check_email(case["email"], check_mx=False)
        if result.valid != case["valid"]:
            failures.append((case["email"], "valid", case["valid"], result.valid))
            continue
        if not case["valid"]:
            if result.error_code != case["error_code"]:
                failures.append(
                    (case["email"], "error_code", case["error_code"], result.error_code)
                )
            expected_suggestion = case.get("suggestion")
            if expected_suggestion is not None and result.suggestion != expected_suggestion:
                failures.append(
                    (case["email"], "suggestion", expected_suggestion, result.suggestion)
                )

    assert failures == []


# ---------------------------------------------------------------------------
# _damerau_levenshtein
# ---------------------------------------------------------------------------


def test_damerau_levenshtein_identical_strings():
    assert _damerau_levenshtein("gmail.com", "gmail.com") == 0


def test_damerau_levenshtein_single_substitution():
    assert _damerau_levenshtein("gmail.com", "gmial.com") == 1


def test_damerau_levenshtein_adjacent_transposition_counts_as_one():
    assert _damerau_levenshtein("ab", "ba") == 1


def test_damerau_levenshtein_insertion_and_deletion():
    assert _damerau_levenshtein("gmail.com", "gmai.com") == 1
    assert _damerau_levenshtein("gmail.com", "gmaail.com") == 1


# ---------------------------------------------------------------------------
# suggest_domain_correction
# ---------------------------------------------------------------------------


def test_suggest_domain_correction_catches_typo():
    assert suggest_domain_correction("gmial.com") == "gmail.com"


def test_suggest_domain_correction_catches_bogus_tld():
    assert suggest_domain_correction("gmail.cmo") == "gmail.com"


def test_suggest_domain_correction_never_flags_popular_domain_itself():
    for domain in email_guard._POPULAR_DOMAINS:
        assert suggest_domain_correction(domain) is None


def test_suggest_domain_correction_never_flags_safe_listed_lookalike():
    for domain in email_guard._TYPO_SAFE_LIST:
        assert suggest_domain_correction(domain) is None


def test_suggest_domain_correction_never_flags_unrelated_business_domain():
    assert suggest_domain_correction("mycompany.com") is None
    assert suggest_domain_correction("acme-corp.co") is None


def test_suggest_domain_correction_bogus_tld_requires_exact_label_match():
    # "myco.cmo" has a bogus TLD but "myco" matches no popular domain's label,
    # so it must not be "corrected" into an unrelated popular domain.
    assert suggest_domain_correction("myco.cmo") is None


# ---------------------------------------------------------------------------
# load_extra_disposable_domains
# ---------------------------------------------------------------------------


def test_load_extra_disposable_domains_blank_path_returns_empty():
    assert load_extra_disposable_domains("") == frozenset()


def test_load_extra_disposable_domains_missing_file_returns_empty():
    assert load_extra_disposable_domains("/no/such/path/does-not-exist.txt") == frozenset()


def test_load_extra_disposable_domains_parses_file_skipping_comments_and_blanks(tmp_path):
    path = tmp_path / "extra_disposable.txt"
    path.write_text("# comment\n\nEvilMail.example\nanother-one.example\n   \n")
    assert load_extra_disposable_domains(str(path)) == {"evilmail.example", "another-one.example"}


@pytest.mark.asyncio
async def test_extra_disposable_domain_is_rejected():
    extra = frozenset({"custom-throwaway.example"})
    result = await check_email(
        "user@custom-throwaway.example", check_mx=False, extra_disposable_domains=extra
    )
    assert result.valid is False
    assert result.error_code == "disposable_email"


# ---------------------------------------------------------------------------
# MX/A reachability layer (monkeypatched - never touches live DNS)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_email_passes_when_mx_resolves_ok(monkeypatch):
    async def fake_check_mx(domain, timeout):
        return "ok"

    monkeypatch.setattr(email_guard, "_check_mx", fake_check_mx)
    result = await check_email("user@realcompany.example", check_mx=True)
    assert result.valid is True
    assert result.mx_warning is None


@pytest.mark.asyncio
async def test_check_email_blocks_when_domain_confirmed_unreachable(monkeypatch):
    async def fake_check_mx(domain, timeout):
        return "unreachable"

    monkeypatch.setattr(email_guard, "_check_mx", fake_check_mx)
    result = await check_email("user@doesnotexist.example", check_mx=True)
    assert result.valid is False
    assert result.error_code == "email_domain_unreachable"


@pytest.mark.asyncio
async def test_check_email_fails_open_on_unknown_mx_status(monkeypatch):
    async def fake_check_mx(domain, timeout):
        return "unknown"

    monkeypatch.setattr(email_guard, "_check_mx", fake_check_mx)
    result = await check_email("user@flaky-resolver.example", check_mx=True)
    assert result.valid is True
    assert result.mx_warning is not None


@pytest.mark.asyncio
async def test_check_email_skips_mx_lookup_entirely_when_disabled(monkeypatch):
    async def explode(domain, timeout):
        raise AssertionError("_check_mx must not be called when check_mx=False")

    monkeypatch.setattr(email_guard, "_check_mx", explode)
    result = await check_email("user@anything.example", check_mx=False)
    assert result.valid is True


# ---------------------------------------------------------------------------
# Negative controls: disabling each guard layer on purpose must make the
# guard fail to catch the exact case it exists to catch.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_negative_control_syntax_guard(monkeypatch):
    """Without the email_validator syntax check, a malformed address slips through."""

    class _FakeValidated:
        normalized = "not-an-email"
        ascii_domain = "invalid"

    monkeypatch.setattr(email_guard, "validate_email", lambda email, **kw: _FakeValidated())
    result = await check_email("not-an-email", check_mx=False)
    assert result.valid is True  # proves the real syntax check is what blocks this normally


@pytest.mark.asyncio
async def test_negative_control_disposable_guard(monkeypatch):
    """With the disposable-domain list emptied, a known disposable address passes."""
    monkeypatch.setattr(email_guard, "_DISPOSABLE_DOMAINS", frozenset())
    result = await check_email("bob@mailinator.com", check_mx=False)
    assert result.valid is True  # proves _DISPOSABLE_DOMAINS is what blocks this normally


@pytest.mark.asyncio
async def test_negative_control_typo_guard(monkeypatch):
    """With the popular-domain list emptied, a typo'd domain is no longer flagged."""
    monkeypatch.setattr(email_guard, "_POPULAR_DOMAINS", ())
    result = await check_email("user@gmial.com", check_mx=False)
    assert result.valid is True  # proves _POPULAR_DOMAINS normally drives this block


@pytest.mark.asyncio
async def test_negative_control_mx_guard(monkeypatch):
    """Forcing _check_mx to always report "ok" lets an unreachable domain through."""

    async def always_ok(domain, timeout):
        return "ok"

    monkeypatch.setattr(email_guard, "_check_mx", always_ok)
    result = await check_email("user@genuinely-unreachable.example", check_mx=True)
    assert result.valid is True  # proves the real MX lookup is what blocks unreachable domains


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def test_record_email_block_metric_increments_both_counters():
    before_specific = _email_block_total("likely_email_typo")
    before_aggregate = _guardrail_block_total("email")

    record_email_block_metric("likely_email_typo")

    assert _email_block_total("likely_email_typo") == before_specific + 1
    assert _guardrail_block_total("email") == before_aggregate + 1
