import json
from pathlib import Path

from app.core.metrics import GUARDRAIL_BLOCKS_TOTAL, PII_REDACTIONS_TOTAL
from app.guardrails.pii import scan_pii, scan_pii_in_data

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Verhoeff-valid synthetic Aadhaar numbers (brute-force generated and checksum-verified,
# not real identifiers - see app.guardrails.pii._verhoeff_valid).
AADHAAR_VALID = "104332181962"
AADHAAR_VALID_2 = "001338908383"

# Luhn-valid card numbers (well-known public test numbers, never real).
VISA_VALID = "4111111111111111"
MASTERCARD_VALID = "5500000000000004"
AMEX_VALID = "340000000000009"


def _blocks_total() -> float:
    return GUARDRAIL_BLOCKS_TOTAL.labels(reason="pii")._value.get()


def _redactions_total(category: str) -> float:
    return PII_REDACTIONS_TOTAL.labels(category=category)._value.get()


def test_redacts_plain_email():
    result = scan_pii("contact me at jane.doe@example.com")
    assert result.redacted_text == "contact me at [REDACTED_EMAIL]"
    assert result.categories == ["email"]
    assert result.counts == {"email": 1}
    assert result.found is True


def test_redacts_obfuscated_email():
    result = scan_pii("reach me, jane.doe at example dot com, soon")
    assert result.redacted_text == "reach me, [REDACTED_EMAIL], soon"
    assert result.categories == ["email"]


def test_redacts_ssn():
    result = scan_pii("my ssn is 123-45-6789")
    assert result.redacted_text == "my ssn is [REDACTED_SSN]"
    assert result.categories == ["ssn"]


def test_redacts_luhn_valid_visa_card():
    spaced = f"{VISA_VALID[:4]} {VISA_VALID[4:8]} {VISA_VALID[8:12]} {VISA_VALID[12:]}"
    result = scan_pii(f"card number {spaced} please")
    assert result.categories == ["credit_card"]
    assert "4111" not in result.redacted_text
    assert "[REDACTED_CARD]" in result.redacted_text


def test_redacts_luhn_valid_mastercard_card():
    result = scan_pii(f"mastercard {MASTERCARD_VALID} on file")
    assert result.categories == ["credit_card"]


def test_redacts_luhn_valid_amex_card():
    result = scan_pii(f"amex {AMEX_VALID} is on file")
    assert result.categories == ["credit_card"]


def test_does_not_redact_luhn_invalid_card_shaped_number():
    """Checksum gating: a card-shaped 16-digit run that fails Luhn is left alone."""
    invalid = VISA_VALID[:-1] + "2"  # flips the last digit, breaking the checksum
    result = scan_pii(f"my test number {invalid} failed verification")
    assert result.found is False
    assert invalid in result.redacted_text


def test_redacts_verhoeff_valid_aadhaar():
    result = scan_pii(f"my aadhaar number is {AADHAAR_VALID}")
    assert result.redacted_text == "my aadhaar number is [REDACTED_AADHAAR]"
    assert result.categories == ["aadhaar"]


def test_redacts_verhoeff_valid_aadhaar_with_spacing():
    spaced = f"{AADHAAR_VALID_2[:4]} {AADHAAR_VALID_2[4:8]} {AADHAAR_VALID_2[8:]}"
    result = scan_pii(f"aadhaar: {spaced}")
    assert result.categories == ["aadhaar"]


def test_does_not_redact_verhoeff_invalid_aadhaar_shaped_number():
    """Checksum gating: a 12-digit run that fails Verhoeff is left alone (e.g. a
    sequential id, a timestamp)."""
    for candidate in ("202410031200", "123456789012", "000000000000", "111111111111"):
        result = scan_pii(f"reference number {candidate} recorded")
        assert result.found is False, f"{candidate} should not be treated as PII"


def test_redacts_pan():
    result = scan_pii("my PAN is ABCDE1234F for tax purposes")
    assert result.redacted_text == "my PAN is [REDACTED_PAN] for tax purposes"
    assert result.categories == ["pan"]


def test_redacts_ifsc_when_labeled():
    result = scan_pii("IFSC code is HDFC0001234 for the branch")
    assert result.redacted_text == "IFSC code is [REDACTED_IFSC] for the branch"
    assert result.categories == ["ifsc"]


def test_does_not_redact_ifsc_shaped_string_without_label():
    """Label gating: an IFSC-shaped code with no 'ifsc' keyword nearby is left alone
    (it's generic enough to otherwise be e.g. a product/warehouse code)."""
    result = scan_pii("the warehouse code is HDFC0001234 this week")
    assert result.found is False


def test_redacts_passport_when_labeled():
    result = scan_pii("passport number is M1234567 for verification")
    assert result.redacted_text == "passport number is [REDACTED_PASSPORT] for verification"
    assert result.categories == ["passport"]


def test_does_not_redact_passport_shaped_string_without_label():
    result = scan_pii("the asset tag is M1234567 on the laptop")
    assert result.found is False


def test_redacts_bank_account_when_labeled():
    result = scan_pii("my account number is 123456789012 for the transfer")
    assert result.redacted_text == "my account number is [REDACTED_BANK_ACCOUNT] for the transfer"
    assert result.categories == ["bank_account"]


def test_redacts_bank_account_with_ac_no_label():
    result = scan_pii("A/C No. 9988776655 for the refund")
    assert result.categories == ["bank_account"]


def test_does_not_redact_long_digit_run_without_bank_label():
    """Label gating: a bare 9-18 digit run (an order id, a tracking number) is left
    alone unless the text actually says it's an account number."""
    result = scan_pii("your order id is 220005512345 and will ship tomorrow")
    assert result.found is False


def test_bank_label_gate_does_not_leak_across_an_unrelated_number_far_away():
    """A label mentioned once must not cause every digit run in a long message to be
    redacted - only digit runs within the label's window count (regression test for
    the whole-text label gate this module replaced)."""
    text = (
        "my account number is on file from before; by the way, call me at "
        "9876543210 later, and the order id is 220005512345"
    )
    result = scan_pii(text)
    assert "220005512345" in result.redacted_text  # order id untouched
    assert "bank_account" not in result.categories


def test_redacts_indian_mobile_plain():
    result = scan_pii("call me at 9876543210")
    assert result.redacted_text == "call me at [REDACTED_PHONE_IN]"
    assert result.categories == ["phone_in"]


def test_redacts_indian_mobile_with_country_code_and_spacing():
    result = scan_pii("call me at +91 98765 43210")
    assert result.redacted_text == "call me at [REDACTED_PHONE_IN]"


def test_redacts_indian_mobile_with_country_code_contiguous():
    """Regression: \\b fails between the '1' of '91' and the following digit, so a
    digit-adjacency lookaround (not \\b) is required at the number's edges."""
    result = scan_pii("call me at +919876543210")
    assert result.redacted_text == "call me at [REDACTED_PHONE_IN]"


def test_redacts_indian_mobile_with_leading_zero():
    result = scan_pii("call me at 09876543210")
    assert result.categories == ["phone_in"]


def test_redacts_international_phone_number():
    result = scan_pii("call +44 20 7946 0958 for support")
    assert result.redacted_text == "call [REDACTED_PHONE] for support"
    assert result.categories == ["phone"]


def test_redacts_international_phone_number_with_many_groups():
    result = scan_pii("call +33 1 42 68 53 00 for support")
    assert result.categories == ["phone"]
    assert "68" not in result.redacted_text


def test_redacts_us_phone_number():
    result = scan_pii("call me at 555-123-4567")
    assert result.redacted_text == "call me at [REDACTED_PHONE]"
    assert result.categories == ["phone"]


def test_leaves_clean_text_untouched():
    text = "what is the capital of France?"
    result = scan_pii(text)
    assert result.redacted_text == text
    assert result.categories == []
    assert result.counts == {}
    assert result.found is False


def test_does_not_redact_isbn_or_timestamp_or_sequential_id_shapes():
    """False-positive avoidance: none of these digit-shaped strings are any kind
    of PII, and must survive untouched."""
    candidates = [
        "isbn 9780143127550 is the book code",
        "isbn 9781234567897 is the book code",
        "order id 1234567890123 was placed today",
        "timestamp 20261003120000 recorded",
        "sequence 202410031200001 generated",
        "version 1.2.3.4.5.6.7.8.9.0.1.2 released",
    ]
    for text in candidates:
        result = scan_pii(text)
        assert result.found is False, f"false positive on: {text!r}"
        assert result.redacted_text == text


def test_redacts_multiple_categories_in_one_text():
    text = f"email jane@example.com or call 9876543210, aadhaar {AADHAAR_VALID}"
    result = scan_pii(text)
    assert set(result.categories) == {"email", "phone_in", "aadhaar"}
    assert result.counts == {"email": 1, "phone_in": 1, "aadhaar": 1}


def test_credit_card_is_redacted_whole_not_split_into_a_bogus_aadhaar_fragment():
    """Regression: credit_card must run before aadhaar so a 16-digit card is
    consumed as one span rather than the aadhaar pattern partially matching its
    first 12 digits."""
    result = scan_pii(f"card: {VISA_VALID}")
    assert result.categories == ["credit_card"]
    assert "aadhaar" not in result.categories


def test_scan_pii_increments_legacy_block_counter_and_categorized_counter():
    before_blocks = _blocks_total()
    before_email = _redactions_total("email")

    scan_pii("contact me at someone@example.com")

    assert _blocks_total() == before_blocks + 1
    assert _redactions_total("email") == before_email + 1


def test_scan_pii_does_not_increment_counters_on_clean_text():
    before_blocks = _blocks_total()

    scan_pii("what is the capital of France?")

    assert _blocks_total() == before_blocks


def test_scan_pii_in_data_redacts_every_string_leaf():
    data = {
        "summary": "contact jane@example.com for details",
        "tags": ["ok", "call 9876543210"],
        "count": 3,
        "nested": {"note": f"aadhaar {AADHAAR_VALID}"},
    }
    redacted, result = scan_pii_in_data(data)

    assert redacted["summary"] == "contact [REDACTED_EMAIL] for details"
    assert redacted["tags"] == ["ok", "call [REDACTED_PHONE_IN]"]
    assert redacted["count"] == 3
    assert redacted["nested"]["note"] == "aadhaar [REDACTED_AADHAAR]"
    assert set(result.categories) == {"email", "phone_in", "aadhaar"}
    assert result.redacted_text == ""


def test_scan_pii_in_data_leaves_clean_structure_untouched():
    data = {"a": "nothing sensitive here", "b": [1, 2, "still fine"], "c": None}
    redacted, result = scan_pii_in_data(data)

    assert redacted == data
    assert result.found is False


def test_pii_dataset_meets_pass_bar():
    """Dataset-level pass bar (mirrors tests/unit/test_injection.py's pattern):
    every true-positive case must come back fully redacted with exactly its
    labeled categories (100% TP), and every true-negative case must survive
    byte-for-byte untouched (0% FP)."""
    cases = json.loads((_DATA_DIR / "pii_cases.json").read_text())
    positive = cases["positive"]
    negative = cases["negative"]
    assert len(positive) + len(negative) >= 60

    tp_failures = []
    for case in positive:
        result = scan_pii(case["text"])
        if set(result.categories) != set(case["categories"]):
            tp_failures.append((case["text"], case["categories"], result.categories))
    tp_rate = (len(positive) - len(tp_failures)) / len(positive)
    assert tp_rate == 1.0, f"true-positive rate {tp_rate:.1%}, failures: {tp_failures}"

    fp_failures = [text for text in negative if scan_pii(text).found]
    fp_rate = len(fp_failures) / len(negative)
    assert fp_rate == 0.0, f"false-positive rate {fp_rate:.1%}, failures: {fp_failures}"


def test_scan_pii_in_data_increments_categorized_counter_but_not_legacy_block_counter():
    """Design contract: output-side scanning must not inflate
    guardrail_blocks_total{reason="pii"}, which is specifically documented as
    'blocked before reaching a model' - output has already reached one."""
    before_blocks = _blocks_total()
    before_email = _redactions_total("email")

    scan_pii_in_data({"answer": "reach me at someone-else@example.com"})

    assert _blocks_total() == before_blocks
    assert _redactions_total("email") == before_email + 1
