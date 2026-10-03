"""PII detection + redaction.

Detects, in priority order (longest/most specific/checksum-gated first, so a
looser pattern never re-matches digits a stricter one already consumed):
credit cards (Luhn checksum), Aadhaar (Verhoeff checksum), PAN, IFSC/bank
account/passport (label-gated - only when a nearby keyword appears, since
their raw shapes are too generic on their own), SSN, Indian mobile numbers,
other phone numbers, and emails (plain + obfuscated "name at example dot
com" forms). Checksums and label-gating are the false-positive defense: an
arbitrary 12-digit timestamp or ISBN will not pass the Aadhaar/card checks,
and a bare 9-18 digit run is not treated as a bank account unless the text
actually says so.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.metrics import GUARDRAIL_BLOCKS_TOTAL, PII_REDACTIONS_TOTAL

# --- Verhoeff checksum (used by real Aadhaar numbers) ---

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def _verhoeff_valid(digits: str) -> bool:
    checksum = 0
    for i, ch in enumerate(reversed(digits)):
        checksum = _VERHOEFF_D[checksum][_VERHOEFF_P[i % 8][int(ch)]]
    return checksum == 0


def _luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        value = int(ch)
        if i % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


@dataclass
class PiiScanResult:
    redacted_text: str
    categories: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return bool(self.categories)


# --- Patterns ---

_AADHAAR_RE = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")

_IFSC_LABEL_RE = re.compile(r"\bifsc\b", re.IGNORECASE)
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")

_PASSPORT_LABEL_RE = re.compile(r"\bpassport\b", re.IGNORECASE)
_PASSPORT_RE = re.compile(r"\b[A-Z][0-9]{7}\b")

_BANK_LABEL_RE = re.compile(r"\b(?:account\s*(?:no\.?|number)|a/?c\s*no\.?)\b", re.IGNORECASE)
_BANK_ACCOUNT_RE = re.compile(r"\b\d{9,18}\b")

_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# (?<!\d)/(?!\d) instead of \b on the digit edges: \b doesn't fire between two
# word characters (a bare "+" is non-word, so "+919876543210" with no
# separator has no boundary between the "1" of "91" and the following "9" -
# \b would silently fail to match the embedded number). A digit-adjacency
# lookaround catches contiguous, space-separated, and hyphenated forms alike.
_PHONE_IN_RE = re.compile(r"(?<!\d)(?:\+91[-\s]?|0)?[6-9]\d{4}[-\s]?\d{5}(?!\d)")
_PHONE_INTL_RE = re.compile(r"(?<!\d)\+\d{1,3}(?:[-\s]?\d{1,4}){2,5}(?!\d)")
_PHONE_US_RE = re.compile(r"\b(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_EMAIL_OBFUSCATED_RE = re.compile(
    r"[\w.+-]+\s*(?:\[at\]|\(at\)|\bat\b)\s*[\w-]+"
    r"(?:\s*(?:\[dot\]|\(dot\)|\bdot\b)\s*[\w-]+)+",
    re.IGNORECASE,
)


def _redact(
    text: str,
    pattern: re.Pattern[str],
    category: str,
    placeholder: str,
    counts: dict[str, int],
    *,
    is_valid: Callable[[str], bool] | None = None,
) -> str:
    def _replace(match: re.Match[str]) -> str:
        if is_valid is not None and not is_valid(re.sub(r"[ -]", "", match.group(0))):
            return match.group(0)
        counts[category] = counts.get(category, 0) + 1
        return placeholder

    return pattern.sub(_replace, text)


def _label_gated_redact(
    text: str,
    pattern: re.Pattern[str],
    label_pattern: re.Pattern[str],
    category: str,
    placeholder: str,
    counts: dict[str, int],
    *,
    window: int = 40,
) -> str:
    """Like `_redact`, but only redacts a match if `label_pattern` appears within
    `window` characters of it - not merely anywhere in the whole text. IFSC/bank
    account/passport numbers share a shape with plain IDs, so without this a
    label elsewhere in a long message (e.g. "my account number is ...") could
    cause an unrelated digit run (a phone number, an order id) to be redacted
    too. Checking a window around each match keeps the gate close to its label.
    """

    def _replace(match: re.Match[str]) -> str:
        start = max(0, match.start() - window)
        end = min(len(text), match.end() + window)
        if not label_pattern.search(text[start:end]):
            return match.group(0)
        counts[category] = counts.get(category, 0) + 1
        return placeholder

    return pattern.sub(_replace, text)


def _scan(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    redacted = text

    # Credit card first: its 13-19 digit pattern is longer than Aadhaar's fixed
    # 12, so running it first lets it greedily claim a full card number before
    # Aadhaar's shorter pattern can match a false 12-digit prefix of one.
    redacted = _redact(
        redacted, _CARD_RE, "credit_card", "[REDACTED_CARD]", counts, is_valid=_luhn_valid
    )
    redacted = _redact(
        redacted, _AADHAAR_RE, "aadhaar", "[REDACTED_AADHAAR]", counts, is_valid=_verhoeff_valid
    )
    redacted = _redact(redacted, _PAN_RE, "pan", "[REDACTED_PAN]", counts)

    redacted = _label_gated_redact(
        redacted, _IFSC_RE, _IFSC_LABEL_RE, "ifsc", "[REDACTED_IFSC]", counts
    )
    redacted = _label_gated_redact(
        redacted, _PASSPORT_RE, _PASSPORT_LABEL_RE, "passport", "[REDACTED_PASSPORT]", counts
    )
    redacted = _label_gated_redact(
        redacted,
        _BANK_ACCOUNT_RE,
        _BANK_LABEL_RE,
        "bank_account",
        "[REDACTED_BANK_ACCOUNT]",
        counts,
    )

    redacted = _redact(redacted, _SSN_RE, "ssn", "[REDACTED_SSN]", counts)
    redacted = _redact(redacted, _PHONE_IN_RE, "phone_in", "[REDACTED_PHONE_IN]", counts)
    redacted = _redact(redacted, _PHONE_INTL_RE, "phone", "[REDACTED_PHONE]", counts)
    redacted = _redact(redacted, _PHONE_US_RE, "phone", "[REDACTED_PHONE]", counts)
    redacted = _redact(redacted, _EMAIL_RE, "email", "[REDACTED_EMAIL]", counts)
    redacted = _redact(redacted, _EMAIL_OBFUSCATED_RE, "email", "[REDACTED_EMAIL]", counts)

    return redacted, counts


def scan_pii(text: str) -> PiiScanResult:
    """Scan/redact a single block of text - typically a user prompt.

    Increments the legacy `guardrail_blocks_total{reason="pii"}` counter (kept
    for the existing /metrics summary and dashboards) plus the categorized
    `pii_redactions_total{category}` counter, exactly once per call when any
    category matched.
    """
    redacted, counts = _scan(text)
    categories = sorted(counts)
    if categories:
        GUARDRAIL_BLOCKS_TOTAL.labels(reason="pii").inc()
        for category in categories:
            PII_REDACTIONS_TOTAL.labels(category=category).inc(counts[category])
    return PiiScanResult(redacted_text=redacted, categories=categories, counts=counts)


def scan_pii_in_data(data: dict[str, Any]) -> tuple[dict[str, Any], PiiScanResult]:
    """Recursively scan/redact every string leaf of a validated output dict.

    Used on model output - a validated dict whose field values may nest
    further dicts/lists/primitives - rather than a single block of text. Each
    string leaf is scanned independently; matches still increment
    `pii_redactions_total{category}` (its help text covers both prompt and
    output), but deliberately do NOT touch `guardrail_blocks_total{reason="pii"}`,
    which is specifically about requests blocked/redacted before reaching a
    model.
    """
    merged: dict[str, int] = {}

    def _walk(value: object) -> object:
        if isinstance(value, str):
            redacted_leaf, counts = _scan(value)
            for category, count in counts.items():
                merged[category] = merged.get(category, 0) + count
            return redacted_leaf
        if isinstance(value, dict):
            return {key: _walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_walk(item) for item in value]
        return value

    redacted = {key: _walk(item) for key, item in data.items()}
    categories = sorted(merged)
    for category in categories:
        PII_REDACTIONS_TOTAL.labels(category=category).inc(merged[category])

    return redacted, PiiScanResult(redacted_text="", categories=categories, counts=merged)
