import json
import logging
from typing import Optional

import httpx
from google import genai
from google.genai import types

from config import get_settings
from schemas import LLMPageTypeResult, LLMMisinfoResult

logger = logging.getLogger(__name__)


def _get_client() -> Optional[genai.Client]:
    settings = get_settings()
    if not settings.gemini_api_key:
        logger.warning("No Gemini API key - LLM features disabled")
        return None
    
    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=settings.llm_timeout * 1000),  # timeout in ms
    )


def _safe_parse_json(text: str) -> Optional[dict]:
    """Próbuje wyciągnąć JSON z odpowiedzi LLM (nawet jeśli jest owinięty w markdown)."""
    text = text.strip()

    # Usuń markdown code block
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Próba wyciągnięcia JSONa z tekstu
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    return None


# ============================
# PAGE TYPE CLASSIFICATION
# ============================

PAGE_TYPE_PROMPT = """You are a webpage classifier. Classify this webpage into EXACTLY ONE category.

Categories:
- news: factual news reporting from a media outlet
- opinion: opinion piece, editorial, commentary
- blog: personal blog post or informal article
- satire: satirical, humorous, parodic content
- poetry: poetry, literary work, creative writing
- forum: forum discussion, comments section, Q&A
- commercial: e-commerce, product page, advertisement, corporate site
- scientific: academic paper, research article, scientific publication
- government: official government or institutional page
- unknown: cannot determine

INPUT:
Title: {title}
Site name: {site_name}
Meta description: {description}
OG type: {og_type}
Language: {lang}
Text excerpt (first 1500 chars):
{text_excerpt}

Return ONLY valid JSON, no other text:
{{"page_type": "...", "confidence": 0.0, "rationale": "one sentence explanation"}}"""


async def classify_page_type(
    title: str,
    text: str,
    meta: dict,
) -> LLMPageTypeResult:
    """Klasyfikuje typ strony przez LLM."""
    client = _get_client()

    if client is None:
        return _fallback_page_type(title, text, meta)

    prompt = PAGE_TYPE_PROMPT.format(
        title=title[:200],
        site_name=meta.get("siteName", "N/A"),
        description=meta.get("description", "N/A")[:300],
        og_type=meta.get("ogType", "N/A"),
        lang=meta.get("lang", "N/A"),
        text_excerpt=text[:1500],
    )

    try:
        settings = get_settings()
        
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=200,
            ),
        )

        content = response.text or ""
        parsed = _safe_parse_json(content)

        if parsed and "page_type" in parsed:
            valid_types = [
                "news", "opinion", "blog", "satire", "poetry",
                "forum", "commercial", "scientific", "government", "unknown",
            ]
            pt = parsed["page_type"].lower().strip()
            if pt not in valid_types:
                pt = "unknown"

            return LLMPageTypeResult(
                page_type=pt,
                confidence=min(max(float(parsed.get("confidence", 0.5)), 0), 1),
                rationale=str(parsed.get("rationale", "")),
            )

    except TimeoutError:
        logger.warning("LLM timeout for page type classification")
    except Exception as e:
        logger.error(f"LLM page type error: {e}")

    return _fallback_page_type(title, text, meta)


def _fallback_page_type(title: str, text: str, meta: dict) -> LLMPageTypeResult:
    """Prosta heurystyka gdy LLM niedostępny."""
    og_type = (meta.get("ogType") or "").lower()
    description = (meta.get("description") or "").lower()
    title_lower = title.lower()
    text_lower = text[:3000].lower() if text else ""

    if og_type == "article":
        return LLMPageTypeResult(page_type="news", confidence=0.4, rationale="og:type=article")

    if og_type == "product":
        return LLMPageTypeResult(page_type="commercial", confidence=0.6, rationale="og:type=product")

    # Heurystyki proste
    if any(w in title_lower for w in ["sklep", "shop", "buy", "kup", "cena", "price", "cart"]):
        return LLMPageTypeResult(page_type="commercial", confidence=0.4, rationale="Commercial keywords in title")

    if any(w in title_lower for w in ["forum", "dyskusja", "discussion", "thread", "wątek"]):
        return LLMPageTypeResult(page_type="forum", confidence=0.4, rationale="Forum keywords in title")

    if any(w in title_lower for w in ["opinia", "komentarz", "opinion", "editorial", "felieton"]):
        return LLMPageTypeResult(page_type="opinion", confidence=0.4, rationale="Opinion keywords")

    return LLMPageTypeResult(page_type="unknown", confidence=0.2, rationale="Could not classify (LLM unavailable)")


# ============================
# MISINFO PATTERN DETECTION
# ============================

MISINFO_PROMPT = """You are analyzing a webpage for communication patterns commonly associated with misinformation.

IMPORTANT:
- Do NOT determine whether the claims are TRUE or FALSE
- Only identify COMMUNICATION PATTERNS and structural signals
- Be conservative - only flag clear patterns

Possible labels (choose ALL that apply, or "none_detected"):
- sensationalism: exaggerated, emotionally charged language designed to provoke strong reactions
- manipulative_framing: biased presentation, cherry-picked facts, misleading context
- conspiracy_cues: conspiracy theory language, unfounded claims about hidden actors
- missing_sourcing: claims without evidence, no citations, no verifiable references
- authority_mimicry: fake expertise signals, pseudo-scientific language, false credentials
- unverified_claims: specific factual claims presented without supporting evidence
- satire_parody: content is clearly satirical or parodic (not misinformation)
- none_detected: no significant misinformation-related patterns found

INPUT:
Title: {title}
Author: {author}
Published: {published}
Site: {site_name}

Heuristic signals already detected by automated analysis:
{signals}

Text excerpt:
{text_excerpt}

Return ONLY valid JSON, no other text:
{{"labels": ["label1", "label2"], "confidence": 0.0, "explanations": ["explanation1", "explanation2"]}}"""


# async def detect_misinfo_patterns(
#     title: str,
#     text: str,
#     meta: dict,
#     heuristic_signals: list[str],
# ) -> LLMMisinfoResult:
#     """Wykrywa wzorce dezinformacyjne przez LLM."""
#     client = _get_client()

#     if client is None:
#         return _fallback_misinfo(heuristic_signals)

#     signals_str = "\n".join(f"- {s}" for s in heuristic_signals) if heuristic_signals else "- No automated signals detected"

#     prompt = MISINFO_PROMPT.format(
#         title=title[:200],
#         author=meta.get("author", "N/A"),
#         published=meta.get("publishedTime", "N/A"),
#         site_name=meta.get("siteName", "N/A"),
#         signals=signals_str,
#         text_excerpt=text[:3000],
#     )

#     try:
#         settings = get_settings()
        
#         response = await client.aio.models.generate_content(
#             model=settings.gemini_model,
#             contents=prompt,
#             config=types.GenerateContentConfig(
#                 temperature=0.2,
#                 max_output_tokens=500,
#             ),
#         )

#         content = response.text or ""
#         parsed = _safe_parse_json(content)

#         if parsed and "labels" in parsed:
#             valid_labels = [
#                 "sensationalism", "manipulative_framing", "conspiracy_cues",
#                 "missing_sourcing", "authority_mimicry", "unverified_claims",
#                 "satire_parody", "none_detected",
#             ]
#             labels = [l for l in parsed["labels"] if l in valid_labels]
#             if not labels:
#                 labels = ["none_detected"]

#             explanations = parsed.get("explanations", [])
#             if isinstance(explanations, list):
#                 explanations = [str(e) for e in explanations[:6]]
#             else:
#                 explanations = []

#             return LLMMisinfoResult(
#                 labels=labels,
#                 confidence=min(max(float(parsed.get("confidence", 0.5)), 0), 1),
#                 explanations=explanations,
#             )

#     except TimeoutError:
#         logger.warning("LLM timeout for misinfo detection")
#     except Exception as e:
#         logger.error(f"LLM misinfo error: {e}")

#     return _fallback_misinfo(heuristic_signals)

async def detect_misinfo_patterns(
    title: str,
    text: str,
    meta: dict,
    heuristic_signals: list[str],
) -> LLMMisinfoResult:
    return _fallback_misinfo(heuristic_signals)

def _fallback_misinfo(signals: list[str]) -> LLMMisinfoResult:
    """Fallback gdy LLM niedostępny - opieramy się na heurystykach."""
    labels = []
    explanations = []

    signal_text = " ".join(signals).lower()

    if "emotional" in signal_text or "clickbait" in signal_text or "exclamation" in signal_text:
        labels.append("sensationalism")
        explanations.append("Automated analysis detected elevated emotional language")

    if "conspiracy" in signal_text:
        labels.append("conspiracy_cues")
        explanations.append("Conspiracy-related language patterns were detected")

    if "no external" in signal_text or "no reference" in signal_text:
        labels.append("missing_sourcing")
        explanations.append("No external sources or citations were found")

    if not labels:
        labels = ["none_detected"]
        explanations = ["No significant patterns detected (limited analysis - LLM unavailable)"]

    return LLMMisinfoResult(
        labels=labels,
        confidence=0.3,
        explanations=explanations,
    )
