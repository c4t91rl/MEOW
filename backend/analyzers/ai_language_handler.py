"""
ai_language_handler.py - Warstwa AI analizy języka (Gemini)

Semantyczna ocena kontekstowa tekstu:
  • wulgarność (z uwzględnieniem kontekstu i eufemizmów)
  • negatywność (ogólny wydźwięk, nie tylko słowa kluczowe)
  • emocjonalność (manipulacja emocjami, sensacyjność)
  • spekulatywność (brak źródeł, domysły, pogłoski)
  • pewność oceny (confidence)

Wykorzystuje Google Gemini API.
Klucze konfiguracyjne: GEMINI_API_KEY, GEMINI_MODEL w ../.env
"""

import json
import logging
from typing import Optional

from google import genai
from google.genai import types

from config import get_settings
from schemas import AILanguageScores

logger = logging.getLogger(__name__)

# ╔══════════════════════════════════════════════════════════════╗
# ║                     KLIENT GEMINI                            ║
# ╚══════════════════════════════════════════════════════════════╝

def _get_client() -> Optional[genai.Client]:
    """Tworzy klienta Gemini na podstawie ustawień z ../.env"""
    settings = get_settings()
    if not settings.gemini_api_key:
        logger.warning("Brak GEMINI_API_KEY - analiza AI języka wyłączona")
        return None

    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(
            timeout=settings.llm_timeout * 1000,  # ms
        ),
    )


# ╔══════════════════════════════════════════════════════════════╗
# ║                       PROMPT                                 ║
# ╚══════════════════════════════════════════════════════════════╝

LANGUAGE_ANALYSIS_PROMPT = """\
You are an expert linguistic analyst evaluating the COMMUNICATION STYLE of a text.
You do NOT judge whether claims are true or false - only HOW they are expressed.

For each axis, return a float score from 0.0 (none) to 1.0 (extreme).

AXES:

1. **vulgarity** (0.0–1.0)
   Profanity, obscenities, slurs, crude language, aggressive insults.
   Consider euphemisms, masked swear words (e.g. "f***", "sh!t", "k*rwa"),
   and contextual offensiveness (e.g. slurs used casually).
   0.0 = perfectly clean language
   0.3 = occasional mild profanity ("damn", "hell", "cholera")
   0.6 = frequent or moderate profanity
   1.0 = pervasive strong profanity, slurs, extreme vulgarity

2. **negativity** (0.0–1.0)
   Overall negative emotional valence: pessimism, doom, hostility, despair,
   contempt, disgust, anger. Consider not just keywords but the overall
   tone and framing.
   0.0 = neutral or positive tone
   0.3 = mildly negative, critical but fair
   0.6 = predominantly negative, hostile or alarmist
   1.0 = overwhelmingly toxic, hateful, despairing

3. **emotionality** (0.0–1.0)
   Degree of emotional manipulation and sensationalism.
   Includes: loaded language, appeal to fear/outrage/sympathy,
   dramatic exaggeration, clickbait rhetoric, emotional blackmail.
   0.0 = dry, factual, measured
   0.3 = slightly emotive but appropriate (e.g. human interest story)
   0.6 = clearly emotionally charged, manipulative framing
   1.0 = extreme emotional manipulation, pure sensationalism

4. **speculativeness** (0.0–1.0)
   Unsupported claims, rumor-spreading, conspiracy-adjacent reasoning,
   hedged language masking opinion as fact, lack of sourcing.
   0.0 = well-sourced, evidence-based, clear attribution
   0.3 = some hedging or unattributed claims
   0.6 = largely speculative, multiple unsourced claims
   1.0 = pure speculation, conspiracy language, no evidence

5. **confidence** (0.0–1.0)
   How confident are you in your assessment?
   Lower if the text is very short, ambiguous, multilingual, or
   if the genre is hard to determine. Also lower for edge cases.
   0.3 = uncertain (very short text, unclear context)
   0.6 = moderate confidence
   0.9 = high confidence (clear, substantial text)

INPUT:
Title: {title}
Text (first 3000 chars):
{text_excerpt}

Return ONLY valid JSON, no other text:
{{"vulgarity": 0.0, "negativity": 0.0, "emotionality": 0.0, "speculativeness": 0.0, "confidence": 0.0}}
"""


# ╔══════════════════════════════════════════════════════════════╗
# ║                  PARSOWANIE ODPOWIEDZI                       ║
# ╚══════════════════════════════════════════════════════════════╝

def _safe_parse_json(text: str) -> Optional[dict]:
    """Wyciąga JSON z odpowiedzi LLM (nawet z markdown code block)."""
    text = text.strip()

    # Usuń markdown ```json ... ```
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: wyciągnij pierwszy obiekt JSON
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    return None


def _clamp(value, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp wartości do zakresu [lo, hi]."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(lo, min(hi, v))


def _parse_scores(parsed: dict) -> Optional[AILanguageScores]:
    """Waliduje i buduje AILanguageScores z rozparsowanego JSON."""
    required_keys = ["vulgarity", "negativity", "emotionality", "speculativeness"]

    if not all(k in parsed for k in required_keys):
        logger.warning(
            "Odpowiedź AI nie zawiera wymaganych kluczy. Otrzymano: %s",
            list(parsed.keys()),
        )
        return None

    return AILanguageScores(
        vulgarity=_clamp(parsed["vulgarity"]),
        negativity=_clamp(parsed["negativity"]),
        emotionality=_clamp(parsed["emotionality"]),
        speculativeness=_clamp(parsed["speculativeness"]),
        confidence=_clamp(parsed.get("confidence", 0.5)),
    )


# ╔══════════════════════════════════════════════════════════════╗
# ║                    GŁÓWNA FUNKCJA                            ║
# ╚══════════════════════════════════════════════════════════════╝

async def analyze_language_ai(
    text: str,
    title: str,
) -> Optional[AILanguageScores]:
    """
    Wysyła tekst do Gemini i zwraca semantyczne oceny języka.

    Zwraca None gdy:
    - brak klucza API
    - timeout
    - błąd parsowania
    - nieprawidłowa odpowiedź
    """
    if not text or not text.strip():
        logger.debug("Pusty tekst - pomijam analizę AI języka")
        return None

    client = _get_client()
    if client is None:
        return None

    # Ogranicz długość tekstu do promptu
    text_excerpt = text[:3000]
    title_clean = (title or "").strip()[:200]

    prompt = LANGUAGE_ANALYSIS_PROMPT.format(
        title=title_clean if title_clean else "(brak tytułu)",
        text_excerpt=text_excerpt,
    )

    try:
        settings = get_settings()

        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,  # niska - chcemy deterministycznych ocen
                max_output_tokens=300,
            ),
        )

        raw_text = response.text or ""
        logger.debug("Odpowiedź AI (language): %s", raw_text[:500])

        parsed = _safe_parse_json(raw_text)
        if parsed is None:
            logger.warning(
                "Nie udało się sparsować JSON z odpowiedzi AI: %s",
                raw_text[:300],
            )
            return None

        scores = _parse_scores(parsed)
        if scores is None:
            return None

        logger.info(
            "AI language scores: vul=%.2f neg=%.2f emo=%.2f spec=%.2f conf=%.2f",
            scores.vulgarity,
            scores.negativity,
            scores.emotionality,
            scores.speculativeness,
            scores.confidence,
        )

        return scores

    except TimeoutError:
        logger.warning("Timeout podczas analizy AI języka")
        return None
    except Exception as e:
        logger.error("Błąd analizy AI języka: %s", e, exc_info=True)
        return None
