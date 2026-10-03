from app.config import Settings
from app.core.errors import GuardrailError, PiiDetectedError
from app.core.metrics import GUARDRAIL_BLOCKS_TOTAL, INJECTION_BLOCKS_TOTAL
from app.guardrails.injection import detect_prompt_injection
from app.guardrails.pii import PiiScanResult, scan_pii


def guard_prompt(prompt: str, settings: Settings) -> tuple[str, PiiScanResult]:
    match = detect_prompt_injection(prompt)
    if match is not None:
        GUARDRAIL_BLOCKS_TOTAL.labels(reason="injection").inc()
        INJECTION_BLOCKS_TOTAL.labels(category=match.category).inc()
        raise GuardrailError("prompt was blocked by the injection screen")

    scan = scan_pii(prompt)
    if scan.found and settings.pii_mode == "block":
        raise PiiDetectedError(f"prompt was blocked: PII detected ({', '.join(scan.categories)})")
    clean_prompt = scan.redacted_text if settings.pii_mode == "redact" else prompt
    return clean_prompt, scan
