from schemas import (
    AnalyzeResponse,
    Scores,
    PageType,
    LanguageResult,
    SourceResult,
    DomainResult,
    LLMPageTypeResult,
    LLMMisinfoResult,
)


# ============================
# PAGE TYPE MULTIPLIERS
# ============================
# Dla każdego typu strony, jak bardzo liczy się dany sygnał.
# Np. poetry: language_risk * 0.1 — bo emocjonalny język jest naturalny.

TYPE_MULTIPLIERS = {
    "poetry": {
        "language": 0.10,
        "source": 0.20,
        "domain": 1.0,
        "transparency": 0.20,
    },
    "satire": {
        "language": 0.20,
        "source": 0.30,
        "domain": 1.0,
        "transparency": 0.40,
    },
    "opinion": {
        "language": 0.50,
        "source": 0.75,
        "domain": 1.0,
        "transparency": 0.85,
    },
    "blog": {
        "language": 0.70,
        "source": 0.80,
        "domain": 1.0,
        "transparency": 0.80,
    },
    "forum": {
        "language": 0.60,
        "source": 0.50,
        "domain": 1.0,
        "transparency": 0.40,
    },
    "commercial": {
        "language": 0.50,
        "source": 0.40,
        "domain": 1.0,
        "transparency": 0.60,
    },
    "scientific": {
        "language": 0.90,
        "source": 1.0,
        "domain": 1.0,
        "transparency": 1.0,
    },
    "government": {
        "language": 0.80,
        "source": 0.90,
        "domain": 0.80,
        "transparency": 1.0,
    },
    "news": {
        "language": 1.0,
        "source": 1.0,
        "domain": 1.0,
        "transparency": 1.0,
    },
    "unknown": {
        "language": 0.80,
        "source": 0.80,
        "domain": 1.0,
        "transparency": 0.80,
    },
}

# Wagi poszczególnych składowych w overall_risk
WEIGHTS = {
    "language": 0.30,
    "source": 0.30,
    "domain": 0.20,
    "transparency": 0.20,
}


def _get_risk_label(score: int) -> str:
    if score <= 20:
        return "Low Risk"
    if score <= 40:
        return "Moderate Risk"
    if score <= 60:
        return "Elevated Risk"
    if score <= 80:
        return "High Risk"
    return "Critical Risk"


def compute_final_score(
    language: LanguageResult,
    sources: SourceResult,
    domain: DomainResult,
    page_type_result: LLMPageTypeResult,
    misinfo_result: LLMMisinfoResult,
    url: str,
) -> AnalyzeResponse:
    """
    Łączy wszystkie analizy w jeden finalny response.
    """
    page_type = page_type_result.page_type
    multipliers = TYPE_MULTIPLIERS.get(page_type, TYPE_MULTIPLIERS["unknown"])

    # ---- Adjusted component scores ----
    # language_risk: 0=safe, 100=very risky → wyższy = gorszy
    adj_language = language.language_risk * multipliers["language"]

    # source_trust: 0=bad, 100=good → odwracamy: 100-x = risk
    adj_source_risk = (100 - sources.source_trust) * multipliers["source"]

    # domain_trust: 0=bad, 100=good → odwracamy
    adj_domain_risk = (100 - domain.domain_trust) * multipliers["domain"]

    # transparency: 0=bad, 100=good → odwracamy
    adj_transparency_risk = (100 - sources.transparency) * multipliers["transparency"]

    # ---- Weighted overall risk ----
    overall_risk_raw = (
        WEIGHTS["language"] * adj_language +
        WEIGHTS["source"] * adj_source_risk +
        WEIGHTS["domain"] * adj_domain_risk +
        WEIGHTS["transparency"] * adj_transparency_risk
    )

    # ---- Bonus / penalty z LLM misinfo ----
    misinfo_labels = misinfo_result.labels

    # Penalty za poważne patterny
    serious_patterns = {"conspiracy_cues", "authority_mimicry", "manipulative_framing"}
    moderate_patterns = {"sensationalism", "unverified_claims", "missing_sourcing"}

    misinfo_bonus = 0
    for label in misinfo_labels:
        if label in serious_patterns:
            misinfo_bonus += 8
        elif label in moderate_patterns:
            misinfo_bonus += 4

    # Bonus za satire/parody — zmniejsz ryzyko
    if "satire_parody" in misinfo_labels:
        misinfo_bonus -= 15

    # Bonus za none_detected
    if "none_detected" in misinfo_labels and len(misinfo_labels) == 1:
        misinfo_bonus -= 5

    overall_risk = int(max(0, min(100, overall_risk_raw + misinfo_bonus)))
    risk_label = _get_risk_label(overall_risk)

    # ---- Confidence ----
    # Uśredniona pewność z LLM-ów
    confidences = [page_type_result.confidence, misinfo_result.confidence]
    avg_confidence = sum(confidences) / len(confidences)

    # Obniżamy confidence jeśli brakuje danych
    if domain.security.domain_age_days is None:
        avg_confidence *= 0.9
    if not sources.details.get("author_present", False):
        avg_confidence *= 0.95
    if language.details.get("word_count", 0) < 100:
        avg_confidence *= 0.85

    avg_confidence = round(min(max(avg_confidence, 0.1), 0.99), 2)

    # ---- Explanations ----
    # Zbieramy najważniejsze sygnały ze wszystkich modułów
    all_signals = []
    all_signals.extend(language.signals)
    all_signals.extend(sources.signals)
    all_signals.extend(domain.signals)
    all_signals.extend(misinfo_result.explanations)

    # Filtrujemy „pozytywne" sygnały jeśli ryzyko niskie
    explanations = []
    for s in all_signals:
        if not s:
            continue
        # Nie powtarzaj
        if s not in explanations:
            explanations.append(s)

    # Limit do 8 najbardziej znaczących
    explanations = explanations[:8]

    if not explanations:
        explanations = ["No specific risk signals identified."]

    # ---- Misinfo patterns — filtruj none_detected jeśli są inne ----
    patterns = [l for l in misinfo_labels if l != "none_detected"]
    if not patterns and "none_detected" in misinfo_labels:
        patterns = ["none_detected"]

    # ---- Build response ----
    return AnalyzeResponse(
        overall_risk=overall_risk,
        risk_label=risk_label,
        confidence=avg_confidence,
        page_type=PageType(
            label=page_type_result.page_type,
            confidence=round(page_type_result.confidence, 2),
            rationale=page_type_result.rationale,
        ),
        misinfo_patterns=patterns,
        scores=Scores(
            language_risk=language.language_risk,
            source_trust=sources.source_trust,
            domain_trust=domain.domain_trust,
            transparency=sources.transparency,
        ),
        security=domain.security,
        explanations=explanations,
        analyzed_url=url,
    )