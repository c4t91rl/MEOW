import re
from urllib.parse import urlparse
from schemas import SourceResult


# ============================
# TRUSTED DOMAINS
# ============================
# Nie jest to pełna baza - na hackathon wystarczy.

TRUSTED_DOMAINS = [
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

# Domeny które mogą wyglądać jak źródła, ale nimi nie są
SOCIAL_DOMAINS = [
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "tiktok.com",
    "youtube.com",
    "reddit.com",
    "t.me",
    "telegram.org",
]


def _is_same_domain(host1: str, host2: str) -> bool:
    """Sprawdza czy dwa hosty to ta sama domena (ignoruje subdomeny)."""
    def base(h):
        parts = h.lower().split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return h.lower()
    return base(host1) == base(host2)


def _is_trusted(hostname: str) -> bool:
    hostname = hostname.lower()
    for td in TRUSTED_DOMAINS:
        if hostname.endswith(td):
            return True
    return False


def _is_social(hostname: str) -> bool:
    hostname = hostname.lower()
    for sd in SOCIAL_DOMAINS:
        if hostname.endswith(sd):
            return True
    return False


def analyze_sources(
    url: str,
    links: list[str],
    meta: dict,
    text: str = "",
) -> SourceResult:
    """
    Analizuje jakość źródeł i transparentność strony.
    """
    page_hostname = ""
    try:
        page_hostname = urlparse(url).hostname or ""
    except Exception:
        pass

    external_hosts = set()
    trusted_hosts = set()
    social_hosts = set()
    total_external = 0

    for link in links:
        try:
            parsed = urlparse(link)
            host = parsed.hostname or ""
            if not host:
                continue
            if _is_same_domain(host, page_hostname):
                continue

            external_hosts.add(host)
            total_external += 1

            if _is_trusted(host):
                trusted_hosts.add(host)
            if _is_social(host):
                social_hosts.add(host)
        except Exception:
            continue

    ext_unique = len(external_hosts)
    trusted_count = len(trusted_hosts)
    social_count = len(social_hosts)

    # ---- Meta fields ----
    author = (meta.get("author") or "").strip()
    published_time = (meta.get("publishedTime") or "").strip()
    description = (meta.get("description") or "").strip()
    site_name = (meta.get("siteName") or "").strip()

    author_present = len(author) > 1
    date_present = len(published_time) > 1

    # ---- Heurystyki w tekście ----
    # Szukamy wzorców cytowań
    citation_patterns = [
        r'according to',
        r'as reported by',
        r'study (shows|finds|found|suggests)',
        r'research (shows|finds|found|suggests)',
        r'published in',
        r'źródło:',
        r'według',
        r'jak podaje',
        r'badania (pokazują|wskazują|wykazały)',
        r'opublikowane w',
        r'\[\d+\]',          # [1] style references
        r'et al\.',           # academic citations
    ]
    citation_count = 0
    text_lower = text[:8000].lower() if text else ""
    for pattern in citation_patterns:
        citation_count += len(re.findall(pattern, text_lower))

    # ============================
    # SOURCE TRUST (0-100)
    # ============================
    source_trust = 45  # baseline

    # External links
    if ext_unique == 0:
        source_trust -= 25
    elif ext_unique <= 2:
        source_trust -= 10
    elif ext_unique <= 5:
        source_trust += 5
    elif ext_unique <= 15:
        source_trust += 10
    else:
        source_trust += 15

    # Trusted references
    if trusted_count == 0 and ext_unique > 0:
        source_trust -= 10
    elif trusted_count == 0 and ext_unique == 0:
        source_trust -= 15
    else:
        source_trust += min(trusted_count * 8, 30)

    # Social-only sources
    if social_count > 0 and trusted_count == 0 and ext_unique <= social_count + 1:
        source_trust -= 10

    # Citations in text
    if citation_count > 0:
        source_trust += min(citation_count * 3, 15)

    source_trust = max(0, min(100, source_trust))

    # ============================
    # TRANSPARENCY (0-100)
    # ============================
    transparency = 60  # baseline

    if author_present:
        transparency += 20
    else:
        transparency -= 15

    if date_present:
        transparency += 15
    else:
        transparency -= 10

    if description:
        transparency += 5

    if site_name:
        transparency += 5

    # Długi tekst z dobrą strukturą = bardziej transparentny
    word_count = len(text.split()) if text else 0
    if word_count > 300:
        transparency += 5
    elif word_count < 50:
        transparency -= 10

    transparency = max(0, min(100, transparency))

    # ============================
    # SIGNALS
    # ============================
    signals = []

    if not author_present:
        signals.append("No author information found")
    if not date_present:
        signals.append("No publication date found")
    if ext_unique == 0:
        signals.append("No external links or citations")
    elif trusted_count == 0:
        signals.append("No references to established or institutional sources")
    if trusted_count >= 3:
        signals.append(f"References {trusted_count} established sources")
    if citation_count > 0:
        signals.append(f"Found {citation_count} citation-like patterns in text")
    if social_count > 0 and trusted_count == 0:
        signals.append("External links primarily lead to social media")
    if word_count < 50:
        signals.append("Very short content - limited substance for analysis")

    if not signals:
        signals.append("Source transparency appears adequate")

    return SourceResult(
        source_trust=source_trust,
        transparency=transparency,
        signals=signals,
        details={
            "external_links_unique": ext_unique,
            "external_links_total": total_external,
            "trusted_references": trusted_count,
            "social_references": social_count,
            "author_present": author_present,
            "date_present": date_present,
            "citation_patterns_found": citation_count,
            "word_count": word_count,
            "author": author if author_present else None,
        },
    )