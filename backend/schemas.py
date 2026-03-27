from pydantic import BaseModel, Field
from typing import Optional


# ============================
# REQUEST
# ============================

class PageMeta(BaseModel):
    description: str = ""
    author: str = ""
    ogType: str = ""
    publishedTime: str = ""
    siteName: str = ""
    lang: str = ""


class AnalyzeRequest(BaseModel):
    url: str
    hostname: str = ""
    title: str = ""
    text: str = ""
    links: list[str] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)


# ============================
# RESPONSE
# ============================

class PageType(BaseModel):
    label: str = "unknown"
    confidence: float = 0.0
    rationale: str = ""


class Scores(BaseModel):
    language_trust: int = 0
    source_trust: int = 50
    domain_trust: int = 50
    transparency: int = 50


class Security(BaseModel):
    https: bool = False
    domain_age_days: Optional[int] = None
    suspicious_hostname: bool = False
    registrar: Optional[str] = None
    tld: str = ""


class AnalyzeResponse(BaseModel):
    overall_risk: int = 0
    risk_label: str = "Unknown"
    confidence: float = 0.0
    page_type: PageType = Field(default_factory=PageType)
    misinfo_patterns: list[str] = Field(default_factory=list)
    scores: Scores = Field(default_factory=Scores)
    security: Security = Field(default_factory=Security)
    explanations: list[str] = Field(default_factory=list)
    analyzed_url: str = ""


# ============================
# INTERNAL — Language Analysis
# ============================

class RuleBasedScores(BaseModel):
    """Wyniki z algorytmu regułowego (0.0–1.0 per oś)."""
    vulgarity: float = 0.0
    negativity: float = 0.0
    emotionality: float = 0.0
    speculativeness: float = 0.0
    clickbait: float = 0.0
    conspiracy: float = 0.0
    formatting_abuse: float = 0.0


class AILanguageScores(BaseModel):
    """Wyniki z modelu AI (0.0–1.0 per oś)."""
    vulgarity: float = 0.0
    negativity: float = 0.0
    emotionality: float = 0.0
    speculativeness: float = 0.0
    confidence: float = 0.0


class LanguageResult(BaseModel):
    """Końcowy wynik analizy językowej — JEDNA definicja."""
    language_trust: int = 0

    # Cztery osie oceny (0.0–1.0, im wyżej tym gorzej)
    vulgarity: float = 0.0
    negativity: float = 0.0
    emotionality: float = 0.0
    speculativeness: float = 0.0

    signals: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)

    # Składowe — do debugowania
    rule_based: Optional[RuleBasedScores] = None
    ai_based: Optional[AILanguageScores] = None


# ============================
# INTERNAL — Source & Domain
# ============================

class SourceResult(BaseModel):
    source_trust: int = 50
    transparency: int = 50
    signals: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)


class DomainResult(BaseModel):
    domain_trust: int = 60
    signals: list[str] = Field(default_factory=list)
    security: Security = Field(default_factory=Security)


# ============================
# INTERNAL — LLM Results
# ============================

class LLMPageTypeResult(BaseModel):
    page_type: str = "unknown"
    confidence: float = 0.0
    rationale: str = ""


class LLMMisinfoResult(BaseModel):
    labels: list[str] = Field(default_factory=lambda: ["none_detected"])
    confidence: float = 0.0
    explanations: list[str] = Field(default_factory=list)