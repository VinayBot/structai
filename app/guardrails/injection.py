"""Prompt-injection and system-prompt-extraction detection.

Detection runs on a normalized form of the input (Unicode NFKC, lowercased,
zero-width characters stripped, whitespace collapsed) so case tricks and
invisible-character smuggling don't bypass the regex rules below. A second,
narrower "despaced" check targets letter-spacing obfuscation (``s y s t e m``)
without scanning the whole message for collapsed substrings, which would
otherwise flag ordinary sentences that happen to contain "system prompt" as
a legitimate phrase (e.g. "what's a good system prompt for a bot?").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_ZERO_WIDTH_RE = re.compile(r"[​‌‍⁠﻿]")
_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_WORDS_RE = re.compile(r"[a-z]+")

_LEET_MAP = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
)

# Matches runs of single letters separated by spaces/dashes/dots, e.g.
# "s y s t e m" or "s-y-s-t-e-m", used to smuggle sensitive phrases past
# plain substring/word-boundary checks.
_SPACING_TRICK_RE = re.compile(r"(?:\b[a-z][\s\-.]{1,2}){4,}[a-z]\b")

# Checked only against text spotted by _SPACING_TRICK_RE above, never the
# full message - see module docstring for why.
_OBFUSCATED_SIGNATURES: dict[str, str] = {
    "systemprompt": "prompt_extraction",
    "hiddenprompt": "prompt_extraction",
    "developerprompt": "prompt_extraction",
    "initialprompt": "prompt_extraction",
    "hiddeninstructions": "prompt_extraction",
    "ignorepreviousinstructions": "delimiter_attack",
    "ignoreallinstructions": "delimiter_attack",
    "disregardpriorrules": "delimiter_attack",
    "disregardsystemprompt": "delimiter_attack",
    "developermode": "role_override",
    "danmode": "role_override",
    "jailbreak": "role_override",
}

_JAILBREAK_DEVICE_WORDS = (
    "iphone", "android", "phone", "device", "ios", "firmware", "tablet", "jailbroken",
)

_BARE_PHRASE_ADJECTIVES = {"system", "hidden", "developer"}

_EXTRACT_VERB = (
    r"(tell|show|give|share|reveal|disclose|dump|print|output|repeat|write\s*down|display|written|"
    r"batao|bata\s*do|dikhado|dikha\s*do)"
)

# Verb ... (your|the|my|what|system|hidden|developer|initial|original|configured) NOUN
# The prefix is required (not optional) so bare "instructions"/"prompt" after an
# everyday verb like "give" doesn't trip this - e.g. "Give me instructions to
# bake bread" has no possessive/adjective directly before "instructions". "rules"
# gets its own, narrower prefix set (no bare "the"/"my") since "give me the
# rules of chess" / "the rules for parking" are extremely common and benign.
_PROMPT_EXTRACT_RE = re.compile(
    rf"\b{_EXTRACT_VERB}\b.{{0,40}}\b(your|the|my|what|system|hidden|developer|initial|original|configured)\s+"
    r"(prompt|instructions?|configuration|message)\b"
)
_PROMPT_EXTRACT_RULES_RE = re.compile(
    rf"\b{_EXTRACT_VERB}\b.{{0,40}}\b(your|what|system|hidden|developer|initial|original|configured|prior|these|those|all)\s+"
    r"rules?\b"
)
# Noun before verb, e.g. "system prompt reveal now" or "SyStEm PrOmPt reveal now".
_PROMPT_EXTRACT_REVERSE_RE = re.compile(
    r"\b(system|hidden|developer|initial|original)\s+(prompt|instructions?|rules?)\b"
    r".{0,20}\b(reveal|show|tell|give|share|disclose|dump|print|output|repeat|batao|bolo)\b"
)

_PRINT_ABOVE_RE = re.compile(
    r"\b(print|output|show|repeat|display|dump|give|write)\b.{0,50}"
    r"\b(above|before this|preceding|verbatim)\b"
)

_WHAT_INSTRUCTIONS_RE = re.compile(
    r"\bwhat\b.{0,15}\b(are|were|is)\b.{0,15}\byour\b.{0,15}\b(instructions?|rules?|prompt|guidelines?)\b"
)

_WHAT_TOLD_RE = re.compile(r"\bwhat\b.{0,20}\b(were|was)\b.{0,10}\byou\b.{0,15}\btold\b")

_IGNORE_RE = re.compile(r"\bignore\b.{0,40}\b(instructions?|rules?|guidelines?|prompt)\b")
_DISREGARD_RE = re.compile(r"\bdisregard\b.{0,40}\b(prompt|instructions?|rules?)\b")
_FORGET_RE = re.compile(
    r"\bforget\b.{0,30}\b(your|the)?\s*(previous|prior)?\s*(instructions?|rules?|prompt)\b"
)
_NEW_INSTRUCTIONS_RE = re.compile(r"\bnew\s+instructions\s*:")

_YOU_ARE_NOW_RE = re.compile(r"\byou are (now|no longer)\b")
_DEV_MODE_ATTACK_RE = re.compile(
    r"\b(developer|dan)\s*mode\b"
    r".{0,40}\b(on|activated|no restrictions?|ignore|override|rules?|guidelines?|"
    r"configuration|restrictions?)\b"
)
_ACT_AS_UNFILTERED_RE = re.compile(
    r"\bact as\b.{0,30}\b(unfiltered|unrestricted|without (any )?(restrictions?|filters?|rules?))\b"
)
_NO_RESTRICTIONS_RE = re.compile(r"\bno restrictions?\b")
_DO_ANYTHING_NOW_RE = re.compile(r"\bdo anything now\b")
_BYPASS_RE = re.compile(r"\bbypass\b.{0,30}\b(restrictions?|rules?|filters?)\b")

_TRANSLATE_RE = re.compile(r"\btranslate\b.{0,60}\b(prompt|instructions?)\b")
_ENCODE_FORWARD_RE = re.compile(r"\b(base64|rot13)\b.{0,50}\b(prompt|instructions?)\b")
_ENCODE_BACKWARD_RE = re.compile(r"\b(prompt|instructions?)\b.{0,50}\b(base64|rot13)\b")
_START_REPLY_RE = re.compile(r"\bstart your reply with\b.{0,30}\byou are\b")

_HINGLISH_SUBJECTS = ("apna", "mera", "humara", "sabhi", "sab")
_HINGLISH_NOUNS = ("prompt", "instructions", "instruction", "rules")
_HINGLISH_VERBS = ("batao", "bata", "dikhado", "dikha", "bolo")

_CATEGORY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (_PROMPT_EXTRACT_RE, "prompt_extraction"),
    (_PROMPT_EXTRACT_RULES_RE, "prompt_extraction"),
    (_PROMPT_EXTRACT_REVERSE_RE, "prompt_extraction"),
    (_PRINT_ABOVE_RE, "prompt_extraction"),
    (_WHAT_INSTRUCTIONS_RE, "prompt_extraction"),
    (_WHAT_TOLD_RE, "prompt_extraction"),
    (_TRANSLATE_RE, "encoding_evasion"),
    (_ENCODE_FORWARD_RE, "encoding_evasion"),
    (_ENCODE_BACKWARD_RE, "encoding_evasion"),
    (_START_REPLY_RE, "prompt_extraction"),
    (_IGNORE_RE, "delimiter_attack"),
    (_DISREGARD_RE, "delimiter_attack"),
    (_FORGET_RE, "delimiter_attack"),
    (_NEW_INSTRUCTIONS_RE, "delimiter_attack"),
    (_YOU_ARE_NOW_RE, "role_override"),
    (_DEV_MODE_ATTACK_RE, "role_override"),
    (_ACT_AS_UNFILTERED_RE, "role_override"),
    (_NO_RESTRICTIONS_RE, "role_override"),
    (_DO_ANYTHING_NOW_RE, "role_override"),
    (_BYPASS_RE, "role_override"),
]


@dataclass(frozen=True)
class InjectionMatch:
    category: str
    reason: str


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    text = text.lower()
    return _WHITESPACE_RE.sub(" ", text).strip()


def _collapse(text: str) -> str:
    return _NON_ALNUM_RE.sub("", text.translate(_LEET_MAP))


def detect_prompt_injection(text: str) -> InjectionMatch | None:
    """Return the category/reason of the first injection pattern matched, or None."""
    normalized = _normalize(text)
    if not normalized:
        return None

    words = _WORDS_RE.findall(normalized)
    if len(words) <= 3 and "prompt" in words and any(w in _BARE_PHRASE_ADJECTIVES for w in words):
        return InjectionMatch("prompt_extraction", "bare_phrase")

    for span_match in _SPACING_TRICK_RE.finditer(normalized):
        collapsed_span = _collapse(span_match.group(0))
        for signature, category in _OBFUSCATED_SIGNATURES.items():
            if signature in collapsed_span:
                return InjectionMatch(category, f"obfuscated:{signature}")

    if (
        any(f" {w} " in f" {normalized} " for w in _HINGLISH_SUBJECTS)
        and any(f" {w} " in f" {normalized} " for w in _HINGLISH_NOUNS)
        and any(f" {w} " in f" {normalized} " for w in _HINGLISH_VERBS)
    ):
        return InjectionMatch("prompt_extraction", "hinglish")

    if "jailbreak" in normalized and not any(w in normalized for w in _JAILBREAK_DEVICE_WORDS):
        return InjectionMatch("role_override", "jailbreak")

    for pattern, category in _CATEGORY_PATTERNS:
        if pattern.search(normalized):
            return InjectionMatch(category, pattern.pattern)

    return None


def is_prompt_injection(text: str) -> bool:
    return detect_prompt_injection(text) is not None
