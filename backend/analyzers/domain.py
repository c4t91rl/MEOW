import re
import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from config import get_settings
from schemas import DomainResult, Security


# ============================
# SUSPICIOUS HOSTNAME PATTERNS
# ============================

TYPOSQUAT_PATTERNS = [
    (r"faceb[o0]{2}k", "facebook.com"),
    (r"g[o0]{2,}gle", "google.com"),
    (r"tw[i1]tt[e3]r", "twitter.com"),
    (r"amaz[o0]n", "amazon.com"),
    (r"micr[o0]s[o0]ft", "microsoft.com"),
    (r"y[o0]utub[e3]", "youtube.com"),
    (r"r[e3]dd[i1]t", "reddit.com"),
    (r"w[i1]k[i1]p[e3]d[i1]a", "wikipedia.org"),
    (r"[i1]nstagram", "instagram.com"),
    (r"l[i1]nk[e3]d[i1]n", "linkedin.com"),
]

# KNOWN_LEGIT = [
#     "facebook.com", "google.com", "twitter.com", "x.com",
#     "amazon.com", "microsoft.com", "youtube.com", "reddit.com",
#     "wikipedia.org", "instagram.com", "linkedin.com",
# ]

# zkopiowane z sources.py
KNOWN_LEGIT = [
    # Encyklopedie / wiedza
    "wikipedia.org",
    "britannica.com",
    "scholar.google.com",
    "wolframalpha.com",

    # Nauka / medycyna
    "nature.com",
    "science.org",
    "thelancet.com",
    "nejm.org",
    "pubmed.ncbi.nlm.nih.gov",
    "nih.gov",
    "cdc.gov",
    "who.int",

    # Agencje prasowe
    "reuters.com",
    "apnews.com",
    "afp.com",

    # Rządy
    "gov.pl",
    "gov.uk",
    "gov",
    "europa.eu",
    "un.org",

    # Fact-checking
    "snopes.com",
    "factcheck.org",
    "politifact.com",
    "fullfact.org",
    "demagog.org.pl",

    # Duże media (nie = prawda, ale = transparentne)
    "bbc.com",
    "bbc.co.uk",
    "nytimes.com",
    "theguardian.com",
    "washingtonpost.com",
    "economist.com",

    # Uczelnie
    "edu",
    "edu.pl",
    "ac.uk",

    # Statystyki
    "statista.com",
    "ourworldindata.org",
    "data.worldbank.org",
]
# TLD-y które częściej goszczą spam
RISKY_TLDS = [
    ".xyz", ".top", ".club", ".work", ".click",
    ".buzz", ".gq", ".ml", ".cf", ".tk", ".ga",
    ".icu", ".monster", ".quest", ".surf",
]


def _get_base_domain(hostname: str) -> str:
    parts = hostname.lower().split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return hostname.lower()


def _get_tld(hostname: str) -> str:
    parts = hostname.lower().split(".")
    if len(parts) >= 2:
        return "." + parts[-1]
    return ""


def _check_suspicious(hostname: str) -> tuple[bool, list[str]]:
    hostname_lower = hostname.lower()
    base = _get_base_domain(hostname_lower)
    reasons = []

    # Check if it's a known legit domain
    if base in KNOWN_LEGIT:
        return False, []

    # Typosquatting
    for pattern, legit in TYPOSQUAT_PATTERNS:
        if re.search(pattern, hostname_lower) and base != legit:
            reasons.append(f"Hostname resembles {legit} (possible typosquatting)")
            break

    # Excessive hyphens
    if hostname_lower.count("-") > 3:
        reasons.append("Excessive hyphens in hostname")

    # Very long hostname
    if len(hostname_lower) > 50:
        reasons.append("Unusually long hostname")

    # Very long subdomain chain
    if hostname_lower.count(".") > 4:
        reasons.append("Deep subdomain nesting")

    # Risky TLD
    tld = _get_tld(hostname_lower)
    if tld in RISKY_TLDS:
        reasons.append(f"TLD '{tld}' is commonly associated with spam")

    # Numbers in domain (not IP)
    if re.search(r'\d{4,}', base.split(".")[0]):
        reasons.append("Domain contains long numeric sequences")

    return len(reasons) > 0, reasons


async def _fetch_domain_age(hostname: str) -> tuple[int | None, str | None]:
    """
    Pobiera wiek domeny przez RDAP.
    Zwraca (age_days, registrar) lub (None, None).
    """
    settings = get_settings()
    base_domain = _get_base_domain(hostname)

    try:
        async with httpx.AsyncClient(timeout=settings.domain_check_timeout) as client:
            # Próbujemy RDAP
            resp = await client.get(
                f"https://rdap.org/domain/{base_domain}",
                follow_redirects=True,
            )

            if resp.status_code != 200:
                return None, None

            data = resp.json()

            # Szukamy daty rejestracji
            age_days = None
            for event in data.get("events", []):
                action = event.get("eventAction", "")
                if action == "registration":
                    date_str = event.get("eventDate", "")
                    if date_str:
                        # Parse ISO date
                        reg_date = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )
                        age_days = (datetime.now(timezone.utc) - reg_date).days
                    break

            # Szukamy registrar
            registrar = None
            for entity in data.get("entities", []):
                roles = entity.get("roles", [])
                if "registrar" in roles:
                    # Próbujemy wyciągnąć nazwę
                    vcard = entity.get("vcardArray", [])
                    if isinstance(vcard, list) and len(vcard) > 1:
                        for item in vcard[1]:
                            if isinstance(item, list) and item[0] == "fn":
                                registrar = item[3] if len(item) > 3 else None
                                break
                    if not registrar:
                        handle = entity.get("handle", "")
                        if handle:
                            registrar = handle
                    break

            return age_days, registrar

    except Exception:
        return None, None


async def analyze_domain(url: str) -> DomainResult:
    """
    Analizuje domenę: HTTPS, wiek, podejrzany hostname.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return DomainResult()

    hostname = parsed.hostname or ""
    is_https = parsed.scheme == "https"
    tld = _get_tld(hostname)
    base = _get_base_domain(hostname.lower())

    # Suspicious check (synchronous)
    suspicious, suspicion_reasons = _check_suspicious(hostname)

    # Domain age (async)
    domain_age_days, registrar = await _fetch_domain_age(hostname)

    # ============================
    # DOMAIN TRUST (0-100)
    # ============================
    domain_trust = 55  # baseline

    # HTTPS
    if is_https:
        domain_trust += 15
    else:
        domain_trust -= 30

    # Domain age
    if domain_age_days is not None:
        if domain_age_days < 30:
            domain_trust -= 35
        elif domain_age_days < 90:
            domain_trust -= 25
        elif domain_age_days < 180:
            domain_trust -= 10
        elif domain_age_days < 365:
            domain_trust += 0
        elif domain_age_days < 730:
            domain_trust += 10
        else:
            domain_trust += 20
    else:
        domain_trust-=10
    # Suspicious hostname
    if suspicious:
        domain_trust -= min(len(suspicion_reasons) * 10, 25)

    # Risky TLD
    if tld in RISKY_TLDS:
        domain_trust -= 10

    if base in KNOWN_LEGIT:
        domain_trust=100

    domain_trust = max(0, min(100, domain_trust))

    # ============================
    # SIGNALS
    # ============================
    signals = []

    if not is_https:
        signals.append("Site does not use HTTPS — connection is not encrypted")

    if domain_age_days is not None:
        if domain_age_days < 30:
            signals.append(f"Domain registered only {domain_age_days} days ago — very new")
        elif domain_age_days < 90:
            signals.append(f"Domain is less than 3 months old ({domain_age_days} days)")
        elif domain_age_days > 1825:  # 5+ years
            signals.append(f"Well-established domain (registered {domain_age_days // 365}+ years ago)")
    else:
        signals.append("Could not determine domain registration date")

    if suspicious:
        signals.extend(suspicion_reasons)

    if not signals:
        signals.append("Domain appears normal")

    return DomainResult(
        domain_trust=domain_trust,
        signals=signals,
        security=Security(
            https=is_https,
            domain_age_days=domain_age_days,
            suspicious_hostname=suspicious,
            registrar=registrar,
            tld=tld,
        ),
    )