"""
language_analysis.py

Dwuwarstwowa analiza języka:
  Warstwa 1 — deterministyczna (listy słów, regex, metryki formatowania)
  Warstwa 2 — model AI (semantyczna ocena kontekstowa)
"""

import re
import logging
from schemas import LanguageResult, RuleBasedScores, AILanguageScores

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║                      BAZY SŁÓW                              ║
# ╚══════════════════════════════════════════════════════════════╝

# ────────────── WULGARYZMY ──────────────

VULGAR_PL = [
    # silne
    "kurwa", "kurwy", "kurewski", "kurwica",
    "chuj", "chuja", "chujowy", "chujowe", "chujnia",
    "pierdolić", "pierdolę", "pierdolony", "pierdolnięty",
    "spierdolić", "spierdolił", "spierdolaj", "odpierdolić",
    "jebać", "jebany", "jebane", "jebaniec", "wyjebane",
    "pojebany", "pojebane", "rozjebać", "ujebany",
    "skurwysyn", "skurwiel", "skurwiony",
    "zasraniec", "zasrany", "zasrane",
    "gówno", "gówniany", "gówniane", "gówniarz",
    # umiarkowane
    "dupek", "dupa", "dupny",
    "cholera", "cholerny", "cholerne",
    "debil", "debilny", "debilizm",
    "idiota", "idiotyczny", "idiotyzm",
    "kretyn", "kretyński",
    "głupek", "tępak", "matoł", "bałwan",
    # lekkie (niższe wagi — uwzględniane, ale mniejszy wpływ)
    "kurde", "kurczę", "pierdzielić", "pieprzyć", "pieprzony",
]

VULGAR_EN = [
    # silne
    "fuck", "fucking", "fucked", "fucker", "motherfucker",
    "shit", "shitty", "bullshit", "horseshit",
    "asshole", "arsehole",
    "bitch", "son of a bitch",
    "dick", "dickhead",
    "bastard", "prick",
    "cunt",
    # umiarkowane
    "crap", "crappy",
    "damn", "damned", "goddamn",
    "ass", "dumbass", "jackass",
    "piss", "pissed",
    "screw you", "screw that",
    "wtf", "stfu", "lmao",
    # lekkie
    "suck", "sucks", "sucker",
    "hell", "bloody",
    "moron", "idiot", "imbecile",
]

# ────────────── JĘZYK EMOCJONALNY ──────────────

EMOTIONAL_PL = [
    # alarm / szok
    "szok", "szokujące", "szokująca", "szokujący",
    "pilne", "pilna", "alarm", "alarmujące",
    "przerażające", "przerażający", "przerażająca",
    "straszne", "straszny", "koszmar", "koszmarne",
    "tragedia", "tragiczne", "tragiczny",
    "katastrofa", "katastrofalny", "katastrofalne",
    "dramat", "dramatyczne", "dramatyczny",
    # skandal / hańba
    "skandal", "skandaliczne", "skandaliczny",
    "hańba", "hańbiące", "wstyd", "kompromitacja",
    "afera", "przekręt",
    # manipulacja
    "manipulacja", "manipulują", "manipulowanie",
    "oszustwo", "oszukują", "oszukańczy",
    "kłamstwo", "kłamią", "zakłamanie",
    "propaganda", "propagandowy",
    "cenzura", "cenzurują", "ocenzurowane",
    # zdrada
    "zdrada", "zdrajcy", "zdrajca", "zdradzieckie",
    "wróg", "wrogowie", "wrogi",
    # ukrywanie
    "ukrywają", "ukrywana", "ukrywane", "ukryta",
    "zatajone", "zatajają", "tuszują",
    # clickbait
    "nie uwierzysz", "musisz wiedzieć", "musisz zobaczyć",
    "to musisz przeczytać", "koniecznie zobacz",
    "zaskakujące", "niewiarygodne", "niebywałe",
    "szok i niedowierzanie", "bomba informacyjna",
]

EMOTIONAL_EN = [
    "shocking", "bombshell", "devastating", "terrifying",
    "horrifying", "alarming", "outrageous", "unbelievable",
    "incredible", "insane", "mind-blowing", "jaw-dropping",
    "breaking", "urgent", "emergency", "crisis",
    "scandal", "scandalous", "disgrace", "shameful",
    "corruption", "corrupt", "crooked",
    "propaganda", "manipulation", "brainwashing",
    "censored", "censorship", "suppressed",
    "silenced", "banned", "forbidden knowledge",
    "you won't believe", "you need to see this",
    "must see", "must read", "gone wrong",
    "what happens next", "will shock you",
    "doctors hate", "one weird trick",
    "goes viral", "the internet is going crazy",
]

# ────────────── JĘZYK NEGATYWNY ──────────────

NEGATIVE_PL = [
    "nienawiść", "nienawidzić", "nienawidzę",
    "zniszczenie", "zniszczyć", "zniszczyli",
    "upadek", "upadają", "upadł",
    "klęska", "porażka", "fiasko",
    "zagrożenie", "zagrożony", "niebezpieczeństwo",
    "kryzys", "kryzysowy",
    "bieda", "nędza", "ubóstwo",
    "śmierć", "śmiertelny", "zabić", "zabijają",
    "cierpienie", "ból", "krzywda",
    "beznadziejny", "beznadziejne", "bezsensowny",
    "żałosny", "żałosne", "nędzny",
    "patologia", "patologiczny", "degeneracja",
    "odrazający", "obrzydliwy", "wstrętny",
    "koszmarny", "okropny", "fatalny",
    "gniew", "wściekłość", "furia", "frustracja",
    "rozczarowanie", "zawód", "zdrada",
]

NEGATIVE_EN = [
    "hatred", "hate", "despise", "loathe",
    "destruction", "destroy", "ruined",
    "failure", "disaster", "catastrophe",
    "threat", "danger", "dangerous",
    "poverty", "misery", "suffering",
    "death", "deadly", "kill", "killing",
    "pain", "agony", "torment",
    "hopeless", "pointless", "meaningless",
    "pathetic", "disgusting", "revolting",
    "terrible", "horrible", "awful", "dreadful",
    "anger", "fury", "rage", "frustration",
    "betrayal", "disappointment",
    "toxic", "corrupt", "evil", "vile",
]

# ────────────── JĘZYK SPEKULATYWNY ──────────────

SPECULATIVE_PL = [
    "prawdopodobnie", "być może", "możliwe że",
    "wydaje się", "wygląda na to",
    "rzekomo", "jakoby", "podobno", "ponoć",
    "spekuluje się", "nieoficjalnie",
    "nie wykluczone", "nie wykluczono",
    "źródła twierdzą", "źródła donoszą",
    "anonimowe źródła", "nieznane źródło",
    "wedle niepotwierdzonych", "niepotwierdzone",
    "plotki", "pogłoski", "krążą informacje",
    "mówi się", "słychać że",
    "mogłoby być", "mogłoby się okazać",
    "czyżby", "kto wie", "pytanie brzmi",
    "nie ma dowodów ale", "bez dowodów",
    "sugeruje się", "spekulacja",
    "teoria mówi", "hipoteza zakłada",
]

SPECULATIVE_EN = [
    "allegedly", "reportedly", "supposedly",
    "rumored", "rumoured", "unconfirmed",
    "sources say", "sources claim",
    "anonymous sources", "unnamed sources",
    "it appears", "it seems",
    "might be", "could be", "may be",
    "possibly", "perhaps", "presumably",
    "speculated", "speculation",
    "unverified", "not confirmed",
    "some believe", "some say", "some claim",
    "there are rumors", "word is",
    "according to unconfirmed",
    "it is believed", "it is thought",
    "no evidence but", "without proof",
    "conspiracy theory", "theory suggests",
    "hypothesis", "conjecture",
    "questionable", "dubious", "doubtful",
]

# ────────────── JĘZYK SPISKOWY ──────────────

CONSPIRACY_PL = [
    "spisek", "spiskowcy", "spiskowa",
    "iluminaci", "masoneria", "masoni",
    "nowy porządek świata", "wielki reset",
    "plandemia", "plandemii",
    "chipy", "chipowanie", "mikroczipy",
    "big pharma", "wielka farma",
    "chemtrails", "smugi chemiczne",
    "płaska ziemia",
    "ukryty rząd", "rząd światowy",
    "agenda 2030", "depopulacja",
    "kontrola umysłu",
    "broń biologiczna", "fałszywa flaga",
    "oni kontrolują", "oni rządzą",
    "ukryta prawda", "zakazana wiedza",
]

CONSPIRACY_EN = [
    "illuminati", "freemasons", "freemasonry",
    "new world order", "nwo", "great reset",
    "plandemic", "scamdemic",
    "microchip", "microchipped", "nanobots",
    "big pharma", "big tech censorship",
    "chemtrails", "flat earth",
    "shadow government", "deep state",
    "agenda 2030", "agenda 21", "depopulation",
    "mind control", "mk ultra", "mkultra",
    "5g radiation", "bioweapon",
    "false flag", "crisis actor", "crisis actors",
    "they control", "they are hiding",
    "forbidden knowledge", "suppressed cure",
    "mainstream media won't tell you",
    "do your own research", "dyor",
    "wake up sheeple", "red pill",
]

# ────────────── CLICKBAIT PATTERNS (regex) ──────────────

CLICKBAIT_PATTERNS = [
    # PL
    r"nie uwierzysz",
    r"to musisz zobaczyć",
    r"szokuj[aą]c[eay]",
    r"tego się nie spodziewasz",
    r"oto co się stało",
    r"musisz to wiedzieć",
    r"lekarze nie chcą",
    r"jeden prosty trik",
    r"ten sposób zmieni",
    # EN
    r"you won'?t believe",
    r"what happens next",
    r"will shock you",
    r"doctors hate",
    r"one weird trick",
    r"this is why",
    r"\d+\s+(reasons?|things?|ways?|facts?|secrets?|signs?)\s",
    r"gone wrong",
    r"goes viral",
    r"the internet is",
    r"is this the end",
    r"exposed.{0,10}truth",
    r"everything you know.{0,15}wrong",
]


# ╔══════════════════════════════════════════════════════════════╗
# ║               WARSTWA 1 — ANALIZA REGUŁOWA                  ║
# ╚══════════════════════════════════════════════════════════════╝

def _count_matches(text_lower: str, word_list: list[str]) -> int:
    """Liczy trafienia słów/fraz w tekście."""
    count = 0
    for word in word_list:
        w = word.lower()
        if " " in w:
            count += text_lower.count(w)
        else:
            count += len(re.findall(r"\b" + re.escape(w) + r"\b", text_lower))
    return count


def _clickbait_score(title: str, text_opening: str) -> float:
    """Ile wzorców clickbaitowych pasuje (0.0–1.0)."""
    combined = (title + " " + text_opening).lower()
    hits = sum(
        1 for p in CLICKBAIT_PATTERNS
        if re.search(p, combined, re.IGNORECASE)
    )
    return min(hits / 3.0, 1.0)


def _all_caps_ratio(text: str) -> float:
    words = text.split()
    if not words:
        return 0.0
    caps = sum(1 for w in words if w.isupper() and len(w) > 2 and w.isalpha())
    return caps / len(words)


def _exclamation_density(text: str) -> float:
    if not text:
        return 0.0
    return text.count("!") / (len(text) / 500.0 + 1)


def _ellipsis_density(text: str) -> float:
    if not text:
        return 0.0
    count = text.count("...") + text.count("…")
    return count / (len(text) / 1000.0 + 1)


def _question_headline(title: str) -> bool:
    t = title.strip()
    return t.endswith("?") and len(t.split()) <= 15


def _saturate(value: float, ceiling: float) -> float:
    """Normalizuje wartość do 0.0–1.0, saturując przy ceiling."""
    return min(value / ceiling, 1.0) if ceiling > 0 else 0.0


def rule_based_analysis(text: str, title: str) -> tuple[RuleBasedScores, list[str], dict]:
    """
    Analiza regułowa — deterministyczna, oparta na listach słów
    i wzorcach formatowania.

    Returns:
        (scores, signals, details)
    """
    if not text.strip():
        return (
            RuleBasedScores(),
            ["Brak treści tekstowej do analizy"],
            {},
        )

    text_lower = text.lower()
    title_lower = title.lower()
    word_count = max(len(text.split()), 1)
    per_100 = word_count / 100.0

    # ── Dopasowania słów ──

    vulgar_hits = _count_matches(text_lower, VULGAR_PL + VULGAR_EN)
    emotional_hits = _count_matches(text_lower, EMOTIONAL_PL + EMOTIONAL_EN)
    negative_hits = _count_matches(text_lower, NEGATIVE_PL + NEGATIVE_EN)
    speculative_hits = _count_matches(text_lower, SPECULATIVE_PL + SPECULATIVE_EN)
    conspiracy_hits = _count_matches(text_lower, CONSPIRACY_PL + CONSPIRACY_EN)

    # ── Normalizacja do 0.0–1.0 ──

    vulgarity_score = _saturate(vulgar_hits / per_100, 3.0)
    emotionality_score = _saturate(emotional_hits / per_100, 5.0)
    negativity_score = _saturate(negative_hits / per_100, 5.0)
    speculative_score = _saturate(speculative_hits / per_100, 4.0)
    conspiracy_score = _saturate(conspiracy_hits / per_100, 3.0)

    # ── Clickbait ──

    cb_score = _clickbait_score(title, text[:500])

    # ── Formatowanie ──

    caps_ratio = _all_caps_ratio(text)
    caps_score = _saturate(caps_ratio, 0.1)

    excl_dens = _exclamation_density(text)
    excl_score = _saturate(excl_dens, 3.0)

    ell_dens = _ellipsis_density(text)
    ell_score = _saturate(ell_dens, 3.0)

    title_caps_flag = 1.0 if title.isupper() and len(title) > 10 else 0.0
    title_question_flag = 0.3 if _question_headline(title) else 0.0

    title_emotional = _count_matches(title_lower, EMOTIONAL_PL + EMOTIONAL_EN)
    title_emotional_score = _saturate(title_emotional, 3.0)

    title_vulgar = _count_matches(title_lower, VULGAR_PL + VULGAR_EN)
    title_vulgar_score = _saturate(title_vulgar, 2.0)

    # ── Łączny scoring formatowania ──

    formatting_abuse = min(
        (
            caps_score * 0.3
            + excl_score * 0.3
            + ell_score * 0.15
            + title_caps_flag * 0.15
            + title_question_flag * 0.1
        ),
        1.0,
    )

    # ── Łączna emocjonalność (tekst + tytuł + formatowanie + clickbait) ──

    emotionality_combined = min(
        emotionality_score * 0.5
        + title_emotional_score * 0.2
        + cb_score * 0.2
        + formatting_abuse * 0.1,
        1.0,
    )

    vulgarity_combined = min(
        vulgarity_score * 0.7 + title_vulgar_score * 0.3,
        1.0,
    )

    scores = RuleBasedScores(
        vulgarity=round(vulgarity_combined, 4),
        negativity=round(negativity_score, 4),
        emotionality=round(emotionality_combined, 4),
        speculativeness=round(speculative_score, 4),
        clickbait=round(cb_score, 4),
        conspiracy=round(conspiracy_score, 4),
        formatting_abuse=round(formatting_abuse, 4),
    )

    # ── Sygnały ──

    signals: list[str] = []

    if vulgarity_combined > 0.2:
        signals.append(
            f"Wykryto wulgarny język ({vulgar_hits} trafień)"
        )
    if emotionality_combined > 0.3:
        signals.append(
            f"Podwyższony poziom emocjonalności ({emotional_hits} markerów)"
        )
    if negativity_score > 0.3:
        signals.append(
            f"Negatywny wydźwięk tekstu ({negative_hits} markerów)"
        )
    if speculative_score > 0.2:
        signals.append(
            f"Język spekulatywny / brak twardych źródeł ({speculative_hits} markerów)"
        )
    if conspiracy_score > 0.2:
        signals.append(
            f"Wzorce języka spiskowego ({conspiracy_hits} markerów)"
        )
    if cb_score > 0.3:
        signals.append("Nagłówek / otwarcie w stylu clickbait")
    if caps_score > 0.3:
        signals.append("Nadużywanie WIELKICH LITER")
    if excl_score > 0.4:
        signals.append("Wysoka gęstość wykrzykników")
    if ell_score > 0.3:
        signals.append("Częste wielokropki (taktyka napięcia)")
    if title_caps_flag:
        signals.append("Tytuł w całości napisany wielkimi literami")

    if not signals:
        signals.append("Język neutralny i wyważony")

    # ── Szczegóły ──

    details = {
        "word_count": word_count,
        "vulgar_hits": vulgar_hits,
        "emotional_hits": emotional_hits,
        "negative_hits": negative_hits,
        "speculative_hits": speculative_hits,
        "conspiracy_hits": conspiracy_hits,
        "caps_ratio": round(caps_ratio, 4),
        "exclamation_density": round(excl_dens, 3),
        "ellipsis_density": round(ell_dens, 3),
        "clickbait_score": round(cb_score, 3),
        "title_all_caps": bool(title_caps_flag),
    }

    return scores, signals, details


# ╔══════════════════════════════════════════════════════════════╗
# ║            WARSTWA 2 — ANALIZA AI (delegowana)               ║
# ╚══════════════════════════════════════════════════════════════╝

async def _get_ai_scores(text: str, title: str) -> AILanguageScores | None:
    """
    Wywołuje model AI z ai_handler.py.
    Zwraca None jeśli AI jest niedostępne (fallback na same reguły).
    """
    try:
        from ai_handler import analyze_language_ai

        result = await analyze_language_ai(text, title)
        return result
    except ImportError:
        logger.warning("ai_handler nie jest dostępny — pomijam analizę AI")
        return None
    except Exception as e:
        logger.error("Błąd analizy AI: %s", e, exc_info=True)
        return None


# ╔══════════════════════════════════════════════════════════════╗
# ║                ŁĄCZENIE WYNIKÓW                              ║
# ╚══════════════════════════════════════════════════════════════╝

RULE_WEIGHT = 0.4
AI_WEIGHT = 0.6


def _combine_axis(rule_val: float, ai_val: float | None) -> float:
    """Łączy wynik regułowy i AI dla jednej osi."""
    if ai_val is None:
        return rule_val
    return rule_val * RULE_WEIGHT + ai_val * AI_WEIGHT


def _compute_language_trust(
    vulgarity: float,
    negativity: float,
    emotionality: float,
    speculativeness: float,
    conspiracy: float,
    clickbait: float,
    formatting: float,
) -> int:
    """
    Oblicza końcowy language_trust (0–100).
    100 = język wiarygodny, czysty.
      0 = język mocno podejrzany.
    """
    penalty = (
        vulgarity * 20
        + negativity * 10
        + emotionality * 25
        + speculativeness * 15
        + conspiracy * 20
        + clickbait * 5
        + formatting * 5
    )
    trust = max(0, min(100, 100 - int(penalty)))
    return trust


# ╔══════════════════════════════════════════════════════════════╗
# ║                   GŁÓWNA FUNKCJA                             ║
# ╚══════════════════════════════════════════════════════════════╝

async def analyze_language(text: str, title: str = "") -> LanguageResult:
    """
    Pełna analiza języka — reguły + AI.

    Args:
        text:  pełna treść artykułu / strony
        title: nagłówek

    Returns:
        LanguageResult z końcowym language_trust i czterema osiami
    """
    # ── Warstwa 1: reguły ──
    rule_scores, rule_signals, rule_details = rule_based_analysis(text, title)

    # ── Warstwa 2: AI ──
    ai_scores = await _get_ai_scores(text, title)

    # ── Łączenie osi ──
    vulgarity = _combine_axis(rule_scores.vulgarity, 
                               ai_scores.vulgarity if ai_scores else None)
    negativity = _combine_axis(rule_scores.negativity, 
                                ai_scores.negativity if ai_scores else None)
    emotionality = _combine_axis(rule_scores.emotionality, 
                                  ai_scores.emotionality if ai_scores else None)
    speculativeness = _combine_axis(rule_scores.speculativeness, 
                                     ai_scores.speculativeness if ai_scores else None)

    # ── Trust ──
    language_trust = _compute_language_trust(
        vulgarity=vulgarity,
        negativity=negativity,
        emotionality=emotionality,
        speculativeness=speculativeness,
        conspiracy=rule_scores.conspiracy,
        clickbait=rule_scores.clickbait,
        formatting=rule_scores.formatting_abuse,
    )

    # ── Sygnały — łączymy regułowe + ewentualnie AI ──
    signals = list(rule_signals)
    if ai_scores and ai_scores.confidence < 0.5:
        signals.append("AI: niska pewność oceny — wynik może być nieprecyzyjny")

    # ── Szczegóły ──
    details = {
        **rule_details,
        "ai_available": ai_scores is not None,
        "ai_confidence": round(ai_scores.confidence, 3) if ai_scores else None,
        "weights": {"rule": RULE_WEIGHT, "ai": AI_WEIGHT},
    }

    return LanguageResult(
        language_trust=language_trust,
        vulgarity=round(vulgarity, 3),
        negativity=round(negativity, 3),
        emotionality=round(emotionality, 3),
        speculativeness=round(speculativeness, 3),
        signals=signals,
        details=details,
        rule_based=rule_scores,
        ai_based=ai_scores,
    )


# ── Wersja synchroniczna (tylko reguły, bez AI) ──

def analyze_language_sync(text: str, title: str = "") -> LanguageResult:
    """Wariant synchroniczny — tylko reguły, bez AI."""
    rule_scores, rule_signals, rule_details = rule_based_analysis(text, title)

    language_trust = _compute_language_trust(
        vulgarity=rule_scores.vulgarity,
        negativity=rule_scores.negativity,
        emotionality=rule_scores.emotionality,
        speculativeness=rule_scores.speculativeness,
        conspiracy=rule_scores.conspiracy,
        clickbait=rule_scores.clickbait,
        formatting=rule_scores.formatting_abuse,
    )

    return LanguageResult(
        language_trust=language_trust,
        vulgarity=rule_scores.vulgarity,
        negativity=rule_scores.negativity,
        emotionality=rule_scores.emotionality,
        speculativeness=rule_scores.speculativeness,
        signals=rule_signals,
        details={**rule_details, "ai_available": False},
        rule_based=rule_scores,
        ai_based=None,
    )