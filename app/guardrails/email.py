"""Email registration guardrail.

Four checks, in order, each cheaper/more certain than the next so an obviously
bad address never pays for a DNS round trip:

1. **Syntax** via `email_validator` (RFC-shape, IDN-aware) - independent of
   Pydantic's own `EmailStr` field validation so this module stays correct if
   ever called from somewhere that didn't already go through that field type.
2. **Disposable domains** - a built-in list of well-known throwaway-mail
   providers, merged with an optional file-configurable extra list
   (`Settings.email_disposable_domains_file`) so new ones can be added
   without a code change.
3. **Typo detection against popular providers** - a domain within Damerau-
   Levenshtein distance 2 of a popular free-mail domain (`gmial.com`,
   `yahooo.com`), or sharing a popular domain's name with a mangled TLD
   (`gmail.cmo`), is flagged with a suggested correction rather than silently
   accepted or silently rejected. A safe-list of real look-alike domains
   (`googlemail.com`, regional Microsoft/Yahoo domains, etc.) is checked
   first so those are never flagged.
4. **MX/A reachability** (`dnspython`, default 3s timeout, toggled by
   `Settings.email_check_mx`) - a confirmed NXDOMAIN or a domain with no
   MX/A/AAAA record at all is rejected; a lookup that merely times out or
   errors (resolver unreachable, transient network issue) fails *open*: the
   address is accepted with a non-blocking warning, since blocking real
   signups on a flaky resolver would be worse than letting one bad address
   through.
"""

import asyncio
from dataclasses import dataclass

import dns.resolver
from email_validator import EmailNotValidError, validate_email

from app.core.metrics import EMAIL_GUARDRAIL_BLOCKS_TOTAL, GUARDRAIL_BLOCKS_TOTAL

_DISPOSABLE_DOMAINS = frozenset(
    {
        "mailinator.com",
        "tempmail.com",
        "10minutemail.com",
        "guerrillamail.com",
        "guerrillamailblock.com",
        "yopmail.com",
        "trashmail.com",
        "trashmail.net",
        "throwawaymail.com",
        "getnada.com",
        "sharklasers.com",
        "dispostable.com",
        "maildrop.cc",
        "mintemail.com",
        "fakeinbox.com",
        "mailnesia.com",
        "mailcatch.com",
        "trbvm.com",
        "discard.email",
        "discardmail.com",
        "spamgourmet.com",
        "mytemp.email",
        "moakt.com",
        "temp-mail.org",
        "tempinbox.com",
        "emailondeck.com",
        "mohmal.com",
        "33mail.com",
        "anonbox.net",
        "burnermail.io",
        "dropmail.me",
        "inboxkitten.com",
        "mailpoof.com",
        "spambog.com",
        "tempail.com",
        "tmailinator.com",
        "armyspy.com",
        "cuvox.de",
        "dayrep.com",
        "einrot.com",
        "fleckens.hu",
        "gustr.com",
        "jourrapide.com",
        "rhyta.com",
        "superrito.com",
        "teleworm.us",
        "20minutemail.com",
        "1secmail.com",
        "correotemporal.org",
        "emailfake.com",
        "fakemailgenerator.com",
        "luxusmail.org",
        "nowmymail.com",
        "spam4.me",
        "tempemail.net",
        "throam.com",
        "zetmail.com",
    }
)

# Popular free-mail domains protected by typo detection.
_POPULAR_DOMAINS = (
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "icloud.com",
    "aol.com",
    "protonmail.com",
    "live.com",
    "msn.com",
    "yandex.com",
    "mail.com",
    "zoho.com",
    "gmx.com",
    "me.com",
)

# Real look-alike domains that must never be flagged as a typo of a popular one.
_TYPO_SAFE_LIST = frozenset(
    {
        "googlemail.com",
        "ymail.com",
        "rocketmail.com",
        "hotmail.co.uk",
        "hotmail.fr",
        "hotmail.de",
        "yahoo.co.uk",
        "yahoo.co.in",
        "yahoo.fr",
        "outlook.co.uk",
        "outlook.de",
        "live.co.uk",
        "live.fr",
        "gmx.de",
        "gmx.net",
        "web.de",
        "mail.ru",
        "qq.com",
        "163.com",
        "naver.com",
        "daum.net",
    }
)

# TLDs that aren't real/registrable and only ever mean "typo of .com/.net" when
# paired with a popular provider's exact name - never applied to an unrecognized
# second-level domain, so a legitimate business on an unusual real TLD is unaffected.
_BOGUS_TLDS = frozenset(
    {"cmo", "ocm", "comm", "vom", "xom", "cim", "coom", "clm", "con", "cojm", "comn"}
)


@dataclass(frozen=True)
class EmailCheckResult:
    valid: bool
    normalized_email: str
    error_code: str | None = None
    message: str | None = None
    suggestion: str | None = None
    mx_warning: str | None = None


def _damerau_levenshtein(a: str, b: str) -> int:
    """Optimal-string-alignment distance (adjacent transposition counts as 1
    edit) - sufficient for catching single-swap typos like 'gmali.com'."""
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,
                d[i][j - 1] + 1,
                d[i - 1][j - 1] + cost,
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[la][lb]


def suggest_domain_correction(domain: str) -> str | None:
    """Returns a popular domain this one was likely meant to be, or None."""
    domain = domain.lower()
    if domain in _TYPO_SAFE_LIST or domain in _POPULAR_DOMAINS:
        return None

    best: str | None = None
    best_distance = 3
    for popular in _POPULAR_DOMAINS:
        distance = _damerau_levenshtein(domain, popular)
        if 0 < distance < best_distance:
            best = popular
            best_distance = distance
    if best is not None:
        return best

    if "." in domain:
        label, _, tld = domain.rpartition(".")
        if tld in _BOGUS_TLDS:
            for popular in _POPULAR_DOMAINS:
                plabel, _, _ = popular.rpartition(".")
                if label == plabel:
                    return popular
    return None


def load_extra_disposable_domains(path: str) -> frozenset[str]:
    if not path:
        return frozenset()
    try:
        with open(path, encoding="utf-8") as handle:
            return frozenset(
                line.strip().lower()
                for line in handle
                if line.strip() and not line.strip().startswith("#")
            )
    except OSError:
        return frozenset()


def _resolve_mx_sync(domain: str, timeout: float) -> str:
    """Returns 'ok', 'unreachable', or 'unknown' (fail-open). Runs in a thread
    since dnspython's resolver is synchronous."""
    resolver = dns.resolver.Resolver()
    resolver.lifetime = timeout
    resolver.timeout = timeout
    try:
        resolver.resolve(domain, "MX")
        return "ok"
    except dns.resolver.NXDOMAIN:
        return "unreachable"
    except dns.resolver.NoAnswer:
        for rtype in ("A", "AAAA"):
            try:
                resolver.resolve(domain, rtype)
                return "ok"
            except Exception:  # noqa: BLE001 - any failure here just means "no fallback record"
                continue
        return "unreachable"
    except Exception:  # noqa: BLE001 - timeout, SERVFAIL, resolver misconfig, etc: fail open
        return "unknown"


async def _check_mx(domain: str, timeout: float) -> str:
    return await asyncio.to_thread(_resolve_mx_sync, domain, timeout)


async def check_email(
    email: str,
    *,
    check_mx: bool = True,
    mx_timeout: float = 3.0,
    extra_disposable_domains: frozenset[str] = frozenset(),
) -> EmailCheckResult:
    try:
        validated = validate_email(email, check_deliverability=False)
    except EmailNotValidError as exc:
        return EmailCheckResult(
            valid=False,
            normalized_email=email,
            error_code="invalid_email_syntax",
            message=str(exc),
        )

    normalized = validated.normalized
    domain = validated.ascii_domain.lower()

    if domain in _DISPOSABLE_DOMAINS or domain in extra_disposable_domains:
        return EmailCheckResult(
            valid=False,
            normalized_email=normalized,
            error_code="disposable_email",
            message="disposable email addresses are not allowed",
        )

    corrected_domain = suggest_domain_correction(domain)
    if corrected_domain is not None:
        local_part = normalized.rsplit("@", 1)[0]
        return EmailCheckResult(
            valid=False,
            normalized_email=normalized,
            error_code="likely_email_typo",
            message=f"this looks like it might be a typo of {corrected_domain}",
            suggestion=f"{local_part}@{corrected_domain}",
        )

    mx_warning = None
    if check_mx:
        status = await _check_mx(domain, mx_timeout)
        if status == "unreachable":
            return EmailCheckResult(
                valid=False,
                normalized_email=normalized,
                error_code="email_domain_unreachable",
                message=f"the domain '{domain}' does not appear to accept email",
            )
        if status == "unknown":
            mx_warning = f"could not verify a mail server for '{domain}' (lookup timed out)"

    return EmailCheckResult(valid=True, normalized_email=normalized, mx_warning=mx_warning)


def record_email_block_metric(error_code: str) -> None:
    EMAIL_GUARDRAIL_BLOCKS_TOTAL.labels(reason=error_code).inc()
    GUARDRAIL_BLOCKS_TOTAL.labels(reason="email").inc()
