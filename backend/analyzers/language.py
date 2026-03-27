import re
import math
from schemas import LanguageResult


# ============================
# WORD LISTS
# ============================

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
    # manipulacja / spisek
    "spisek", "spiskowy", "spiskowcy",
    "manipulacja", "manipulują", "manipulowanie",
    "oszustwo", "oszukują", "oszukańczy",
    "kłamstwo", "kłamią", "zakłamanie",
    "propaganda", "propagandowy",
    "cenzura", "cenzurują", "ocenzurowane",
    # zdrada / wrogość
    "zdrada", "zdrajcy", "zdrajca", "zdradzieckie",
    "wróg", "wrogowie", "wrogi",
    # ukrywanie
    "ukrywają", "ukrywana", "ukrywane", "ukryta",
    "zatajone", "zatajają", "tuszują",
    "prawda", "jedyna prawda",
    # clickbait PL
    "nie uwierzysz", "musisz wiedzieć", "musisz zobaczyć",
    "to musisz przeczytać", "koniecznie zobacz",
    "zaskakujące", "niewiarygodne", "niebywałe",
    "szok i niedowierzanie", "bomba informacyjna",
]

EMOTIONAL_EN = [
    # shock / alarm
    "shocking", "bombshell", "devastating", "terrifying",
    "horrifying", "alarming", "outrageous", "unbelievable",
    "incredible", "insane", "mind-blowing", "jaw-dropping",
    "breaking", "urgent", "emergency", "crisis",
    # scandal
    "scandal", "scandalous", "disgrace", "shameful",
    "corruption", "corrupt", "crooked",
    # conspiracy
    "conspiracy", "cover-up", "coverup", "exposed",
    "they don't want you to know", "what they're hiding",
    "the truth about", "wake up", "sheeple",
    "deep state", "new world order", "big pharma",
    "mainstream media lies", "controlled opposition",
    # manipulation
    "propaganda", "manipulation", "brainwashing",
    "censored", "censorship", "suppressed",
    "silenced", "banned", "forbidden knowledge",
    # clickbait EN
    "you won't believe", "you need to see this",
    "must see", "must read", "gone wrong",
    "what happens next", "will shock you",
    "doctors hate", "one weird trick",
    "is this the end", "exposed the truth",
    "goes viral", "the internet is going crazy",
]

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
    "kontrola umysłu", "mind control",
    "5g", "broń biologiczna",
    "fałszywa flaga", "false flag",
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


# ============================
# ANALYSIS
# ============================

def _count_matches(text_lower: str, word_list: list[str]) -> int:
    count = 0
    for word in word_list:
        w = word.lower()
        # szukamy jako substring dla fraz, exact word boundary dla pojedynczych słów
        if " " in w:
            count += text_lower.count(w)
        else:
            count += len(re.findall(r'\b' + re.escape(w) + r'\b', text_lower))
    return count


def _clickbait_score(title: str, text_first_500: str) -> float:
    combined = (title + " " + text_first_500).lower()
    hits = 0
    for pattern in CLICKBAIT_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            hits += 1
    # 0-1, saturates at 3 hits
    return min(hits / 3.0, 1.0)


def _question_headline(title: str) -> bool:
    """Clickbait often uses questions."""
    t = title.strip()
    return t.endswith("?") and len(t.split()) <= 15


def _all_caps_ratio(text: str) -> float:
    words = text.split()
    if len(words) == 0:
        return 0.0
    caps = sum(1 for w in words if w.isupper() and len(w) > 2 and w.isalpha())
    return caps / len(words)


def _exclamation_density(text: str) -> float:
    if len(text) == 0:
        return 0.0
    return text.count("!") / (len(text) / 500.0 + 1)


def _ellipsis_density(text: str) -> float:
    if len(text) == 0:
        return 0.0
    ellipsis_count = text.count("...") + text.count("…")
    return ellipsis_count / (len(text) / 1000.0 + 1)


def _sentence_stats(text: str) -> dict:
    """Średnia długość zdań — bardzo krótkie = clickbait-ish."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    if not sentences:
        return {"avg_sentence_length": 0, "sentence_count": 0}
    lengths = [len(s.split()) for s in sentences]
    return {
        "avg_sentence_length": sum(lengths) / len(lengths),
        "sentence_count": len(sentences),
    }


def analyze_language(text: str, title: str) -> LanguageResult:
    """
    Analizuje tekst pod kątem emocjonalności, clickbaitu, języka spiskowego.
    Zwraca language_trust 0-100.
    """
    if not text.strip():
        return LanguageResult(
            language_trust=0,
            signals=["Page has no readable text content"],
            details={}
        )

    text_lower = text.lower()
    title_lower = title.lower()
    word_count = max(len(text.split()), 1)

    # ---- Emotional words ----
    emotional_hits = _count_matches(text_lower, EMOTIONAL_PL + EMOTIONAL_EN)
    emotional_density = emotional_hits / (word_count / 100.0)
    emotional_score = min(emotional_density / 5.0, 1.0)  # saturuje przy 5 hits / 100 words

    # ---- Conspiracy words ----
    conspiracy_hits = _count_matches(text_lower, CONSPIRACY_PL + CONSPIRACY_EN)
    conspiracy_density = conspiracy_hits / (word_count / 100.0)
    conspiracy_score = min(conspiracy_density / 3.0, 1.0)

    # ---- Clickbait ----
    cb_score = _clickbait_score(title, text[:500])

    # ---- Formatting signals ----
    caps_ratio = _all_caps_ratio(text)
    caps_score = min(caps_ratio / 0.1, 1.0)  # 10% caps words = max

    excl_density = _exclamation_density(text)
    excl_score = min(excl_density / 3.0, 1.0)

    ellipsis_density = _ellipsis_density(text)
    ellipsis_score = min(ellipsis_density / 3.0, 1.0)

    # ---- Title analysis ----
    title_caps = 1.0 if title.isupper() and len(title) > 10 else 0.0
    title_question = 0.3 if _question_headline(title) else 0.0

    # ---- Emotional title words ----
    title_emotional = _count_matches(title_lower, EMOTIONAL_PL + EMOTIONAL_EN)
    title_emotional_score = min(title_emotional / 3.0, 1.0)

    # ---- Sentence stats ----
    sent_stats = _sentence_stats(text[:5000])

    # ============================
    # COMPOSITE SCORE
    # ============================
    # Wagi — co wpływa na language_trust
    language_trust_raw = (
        emotional_score * 25 +
        conspiracy_score * 25 +
        cb_score * 20 +
        caps_score * 8 +
        excl_score * 7 +
        ellipsis_score * 3 +
        title_caps * 5 +
        title_question * 2 +
        title_emotional_score * 5
    )

    language_trust = max(0, min(100, int(language_trust_raw)))

    # ============================
    # SIGNALS (human-readable)
    # ============================
    signals = []

    if emotional_score > 0.3:
        signals.append(
            f"Elevated emotional/alarmist language detected ({emotional_hits} markers)"
        )
    if conspiracy_score > 0.2:
        signals.append(
            f"Conspiracy-related language patterns found ({conspiracy_hits} markers)"
        )
    if cb_score > 0.3:
        signals.append("Clickbait-style headline or opening")
    if caps_score > 0.3:
        signals.append("Excessive use of ALL CAPS in text")
    if excl_score > 0.4:
        signals.append("High density of exclamation marks")
    if title_caps > 0:
        signals.append("Title is entirely uppercase")
    if title_emotional_score > 0.5:
        signals.append("Title contains strong emotional language")
    if ellipsis_score > 0.3:
        signals.append("Frequent use of ellipsis (suspense tactic)")

    if not signals:
        signals.append("Language appears neutral and measured")

    return LanguageResult(
        language_trust=language_trust,
        signals=signals,
        details={
            "emotional_density": round(emotional_score, 3),
            "conspiracy_density": round(conspiracy_score, 3),
            "clickbait_score": round(cb_score, 3),
            "caps_ratio": round(caps_ratio, 4),
            "exclamation_density": round(excl_density, 3),
            "title_all_caps": title_caps > 0,
            "word_count": word_count,
            "emotional_hits": emotional_hits,
            "conspiracy_hits": conspiracy_hits,
            "avg_sentence_length": round(sent_stats["avg_sentence_length"], 1),
        },
    )