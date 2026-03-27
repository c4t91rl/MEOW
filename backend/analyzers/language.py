"""
language_analysis.py — v2 (increased sensitivity)

Dwuwarstwowa analiza języka:
  Warstwa 1 — deterministyczna (listy słów, regex, metryki tekstu)
  Warstwa 2 — model AI (semantyczna ocena kontekstowa)

Zmiany vs v1:
  • Dodano detekcję nieformalności (slang, internet culture)
  • Dodano detekcję toksyczności (hate speech, agresja)
  • Dodano ocenę jakości tekstu (struktura, interpunkcja, słownictwo)
  • Dual scoring: density + absolute (krótkie teksty nie uciekają)
  • Nieliniowa amplifikacja — małe wartości mają większy wpływ
  • Obniżone progi saturacji
  • Wyższe wagi kar
"""

import re
import math
import logging
from schemas import LanguageResult, RuleBasedScores, AILanguageScores

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║                      BAZY SŁÓW                              ║
# ╚══════════════════════════════════════════════════════════════╝

# ────────────── WULGARYZMY ──────────────

VULGAR_PL = [
    "kurwa", "kurwy", "kurewski", "kurwica",
    "chuj", "chuja", "chujowy", "chujowe", "chujnia",
    "pierdolić", "pierdolę", "pierdolony", "pierdolnięty",
    "spierdolić", "spierdolił", "spierdolaj", "odpierdolić",
    "jebać", "jebany", "jebane", "jebaniec", "wyjebane",
    "pojebany", "pojebane", "rozjebać", "ujebany",
    "skurwysyn", "skurwiel", "skurwiony",
    "zasraniec", "zasrany", "zasrane",
    "gówno", "gówniany", "gówniane", "gówniarz",
    "dupek", "dupa", "dupny",
    "cholera", "cholerny", "cholerne",
    "debil", "debilny", "debilizm",
    "idiota", "idiotyczny", "idiotyzm",
    "kretyn", "kretyński",
    "głupek", "tępak", "matoł", "bałwan",
    "kurde", "kurczę", "pierdzielić", "pieprzyć", "pieprzony",
]

VULGAR_EN = [
    "fuck", "fucking", "fucked", "fucker", "motherfucker",
    "shit", "shitty", "bullshit", "horseshit",
    "asshole", "arsehole",
    "bitch", "son of a bitch",
    "dick", "dickhead",
    "bastard", "prick",
    "cunt",
    "crap", "crappy",
    "damn", "damned", "goddamn",
    "ass", "dumbass", "jackass",
    "piss", "pissed",
    "screw you", "screw that",
    "wtf", "stfu",
    "suck", "sucks", "sucker",
    "hell", "bloody",
    "moron", "idiot", "imbecile",
]

# ────────────── JĘZYK EMOCJONALNY ──────────────

EMOTIONAL_PL = [
    "szok", "szokujące", "szokująca", "szokujący",
    "pilne", "pilna", "alarm", "alarmujące",
    "przerażające", "przerażający", "przerażająca",
    "straszne", "straszny", "koszmar", "koszmarne",
    "tragedia", "tragiczne", "tragiczny",
    "katastrofa", "katastrofalny", "katastrofalne",
    "dramat", "dramatyczne", "dramatyczny",
    "skandal", "skandaliczne", "skandaliczny",
    "hańba", "hańbiące", "wstyd", "kompromitacja",
    "afera", "przekręt",
    "manipulacja", "manipulują", "manipulowanie",
    "oszustwo", "oszukują", "oszukańczy",
    "kłamstwo", "kłamią", "zakłamanie",
    "propaganda", "propagandowy",
    "cenzura", "cenzurują", "ocenzurowane",
    "zdrada", "zdrajcy", "zdrajca", "zdradzieckie",
    "wróg", "wrogowie", "wrogi",
    "ukrywają", "ukrywana", "ukrywane", "ukryta",
    "zatajone", "zatajają", "tuszują",
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

# ────────────── NOWE: JĘZYK NIEFORMALNY / SLANG ──────────────

INFORMAL_EN = [
    # internet slang
    "lol", "lmao", "lmfao", "rofl", "roflmao",
    "omg", "omfg", "smh", "fml", "tbh",
    "imo", "imho", "idk", "idc", "idgaf",
    "ngl", "bruh", "fam", "yolo",
    "af", "irl", "tfw", "mfw", "mrw",
    "itt", "inb4", "iirc",
    # chan / board culture
    "anon", "anons",
    "newfag", "oldfag", "samefag",
    "kek", "topkek",
    "based", "redpilled", "blackpilled", "bluepilled",
    "cringe", "cope", "seethe", "mald", "dilate",
    "incel", "simp", "chad", "stacy",
    "normie", "normies",
    "greentext", "copypasta",
    "trips", "dubs", "quads", "digits",
    "sauce", "lurk", "lurker", "lurking",
    "bait", "shitpost", "shitposting",
    "janny", "jannies",
    "soyboy", "soyjak", "wojak", "pepe",
    "btfo", "rekt",
    "cuck", "cucked",
    "coomer", "doomer", "bloomer", "zoomer", "boomer",
    # ogólnie nieformalne
    "gonna", "wanna", "gotta",
    "nah", "yeah", "yep", "nope", "dunno",
    "lemme", "gimme", "kinda", "sorta",
    "haha", "hehe", "xd", "xdd",
    "pls", "plz", "thx", "ty", "np",
    "noob", "pwned", "owned",
    "troll", "trolling", "triggered",
    "cringe", "sus", "sussy", "cap", "no cap",
    "ratio", "skill issue", "get good", "git gud",
    "gg", "ez", "ggez",
    "uwu", "owo",
]

INFORMAL_PL = [
    "xd", "xdd", "xddd", "hehe", "haha", "hihi",
    "lol", "lmao", "rofl",
    "spoko", "nara", "elo", "siema", "hejo", "cześć",
    "mordo", "ziom", "ziomek", "bracie",
    "typ", "typek", "typowa",
    "janusz", "grażyna", "seba", "karyna",
    "git", "gituwa", "ogar", "ogarnij",
    "luzik", "wyluzuj", "chiluj",
    "hajs", "kasa", "szmal",
    "beka", "bekę", "bekowy",
    "cringe", "krindż", "bazowane",
    "cope", "seethe",
    "tbh", "imo", "btw",
    "xddd", "xdddd",
    "dej", "se", "ne", "ta",
    "nie no", "no nie",
    "masakra", "zajebiście", "zajebiste",
    "odlot", "kozak", "kozacki",
    "nara", "papa", "naura",
    "luj", "ziomal", "ziomy",
    "fejk", "fejkowy", "scam",
]

# ────────────── NOWE: TOKSYCZNOŚĆ / HATE SPEECH ──────────────

TOXIC_EN = [
    # dehumanizacja
    "subhuman", "untermensch", "vermin", "parasite", "parasites",
    "cockroach", "cockroaches", "animal", "animals",  # w kontekście obraźliwym
    # agresja bezpośrednia
    "kill yourself", "kys", "neck yourself",
    "go die", "drink bleach", "end yourself",
    "rope yourself",
    # slurs / obelgi grupowe
    "retard", "retarded", "tard", "libtard",
    "faggot", "faggots", "fag", "fags",
    "tranny", "trannies", "troon",
    "whore", "slut", "thot",
    "sperg", "sperging",
    "white trash", "trailer trash",
    "neckbeard", "landwhale",
    # agresywne zwroty
    "stfu", "gtfo", "kys",
    "shut the fuck up", "get the fuck out",
    "eat shit", "go to hell",
    "piece of shit", "waste of space",
    "garbage human", "trash person",
    "scum", "scumbag", "lowlife",
    "degenerate", "degeneracy",
    "filth", "filthy",
]

TOXIC_PL = [
    # agresja bezpośrednia
    "zabij się", "zdychaj", "zdechnij",
    "wypierdalaj", "spierdalaj", "spadaj",
    "wypierdol się", "odpierdol się",
    "zamknij mordę", "zamknij ryj", "zamknij jadaczkę",
    "zamknij się",
    # obelgi
    "pedał", "pedały", "ciota", "cioty",
    "cwel", "cwele",
    "lesba", "lesbo",
    "szmata", "dziwka", "lafirynda",
    "podczłowiek",
    "ścierwo", "szumowina", "szumowiny",
    "śmieć", "śmiecie", "odpad", "odpady",
    "patol", "patole",
    "żul", "żule", "menel", "menele",
    "gnida", "gnidy",
    "robak", "robaki",
    "tłuk", "tłuki",
    "zjeb", "zjeby",
]

# ────────────── NOWE: WZORCE AGRESJI (regex) ──────────────

AGGRESSIVE_PATTERNS_RAW = [
    # EN — bezpośrednie ataki
    r"kill\s+your\s*self",
    r"go\s+(and\s+)?die",
    r"drink\s+bleach",
    r"\bkys\b",
    r"\bstfu\b",
    r"\bgtfo\b",
    r"shut\s+(the\s+)?fuck\s+up",
    r"fuck\s+(you|off|this|that|him|her|them)",
    r"go\s+fuck\s+your",
    r"eat\s+shit",
    r"piece\s+of\s+shit",
    r"waste\s+of\s+(space|oxygen|air|skin)",
    # PL — bezpośrednie ataki
    r"wypierdalaj",
    r"spierdalaj",
    r"zabij\s+się",
    r"zdychaj",
    r"zdechnij",
    r"zamknij\s+(się|mordę|ryj|pysk|jadaczkę)",
    r"wypierdol\s+się",
    r"odpierdol\s+się",
    # Wzorce dehumanizacji
    r"(all|every|these)\s+\w+\s+are\s+(trash|garbage|subhuman|animals|vermin|scum)",
    r"(ludzie|osoby|oni)\s+(to|są)\s+(śmieci|ścierwo|robaki|szumowiny)",
    # Sarkastyczna agresja
    r"nobody\s+(cares|asked)",
    r"who\s+asked",
    r"did\s+i\s+ask",
    r"nikogo\s+(to\s+)?nie\s+obchodzi",
    r"kogo\s+to\s+obchodzi",
]

# ────────────── CLICKBAIT PATTERNS (regex) ──────────────

CLICKBAIT_PATTERNS_RAW = [
    r"nie uwierzysz",
    r"to musisz zobaczyć",
    r"szokuj[aą]c[eay]",
    r"tego się nie spodziewasz",
    r"oto co się stało",
    r"musisz to wiedzieć",
    r"lekarze nie chcą",
    r"jeden prosty trik",
    r"ten sposób zmieni",
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

# ────────────── NOWE: UGC (User-Generated Content) PATTERNS ──────────────

UGC_PATTERNS_RAW = [
    r">>?\d{4,}",                  # >>12345678 (reply quoting)
    r"^>(?!>)\s*\w",               # greentext: > be me
    r"\b(op|OP)\s+(is|here|here's|said|says)\b",
    r"\b(pic|img)\s+related\b",
    r"\b(bump|sage|sticky)\b",
    r"\btl;?dr\b",
    r"\binb4\b",
    r"\bsamefag",
    r"\bnamefag",
    r"\btripfag",
    r"\b(mods?|jannies?)\s+(are|delete|ban)",
    r"\bthis\s+thread\b",
    r"\b(posted?|reply|replies)\s+(from|by)\s+anonymous",
    r"anonymous\s*(\d|ID|#)",
]


# ╔══════════════════════════════════════════════════════════════╗
# ║               PRECOMPILACJA REGEX                            ║
# ╚══════════════════════════════════════════════════════════════╝

_RE_AGGRESSIVE = [re.compile(p, re.IGNORECASE) for p in AGGRESSIVE_PATTERNS_RAW]
_RE_CLICKBAIT = [re.compile(p, re.IGNORECASE) for p in CLICKBAIT_PATTERNS_RAW]
_RE_UGC = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in UGC_PATTERNS_RAW]


# ╔══════════════════════════════════════════════════════════════╗
# ║               HELPER FUNCTIONS                               ║
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


def _count_pattern_hits(text: str, compiled_patterns: list[re.Pattern]) -> int:
    """Liczy ile skompilowanych wzorców regex pasuje do tekstu."""
    return sum(
        1 for p in compiled_patterns
        if p.search(text)
    )


def _saturate(value: float, ceiling: float) -> float:
    """Normalizuje do 0.0–1.0, saturując przy ceiling."""
    if ceiling <= 0:
        return 0.0
    return min(value / ceiling, 1.0)


def _dual_score(
    hits: int,
    per_100: float,
    density_ceiling: float,
    absolute_ceiling: float,
) -> float:
    """
    Podwójny scoring: gęstość + wartość bezwzględna.
    Zapobiega uciekaniu krótkich tekstów z kilkoma trafień.

    Np. 2 wulgaryzmy w 50-słowowym poście:
      density:  (2/0.5) / 1.5 = 2.67 → sat(1.0)
      absolute: 2/4 * 0.6 = 0.3
      wynik: max(1.0, 0.3) = 1.0

    Np. 2 wulgaryzmy w 5000-słowowym artykule:
      density:  (2/50) / 1.5 = 0.027
      absolute: 2/4 * 0.6 = 0.3
      wynik: max(0.027, 0.3) = 0.3
    """
    density = _saturate(hits / per_100, density_ceiling) if per_100 > 0 else 0
    absolute = _saturate(hits, absolute_ceiling) * 0.6
    return min(max(density, absolute), 1.0)


def _amplify(score: float, power: float = 0.65) -> float:
    """
    Nieliniowa amplifikacja — małe wartości stają się bardziej odczuwalne.

    Bez amplifikacji:  0.1 → 0.1   → kara: 2.5 pkt (z 25 max)
    Z amplifikacją:    0.1 → 0.22  → kara: 5.5 pkt

    Przegląd transformacji (power=0.65):
      0.05 → 0.13
      0.10 → 0.22
      0.20 → 0.35
      0.30 → 0.46
      0.50 → 0.64
      0.70 → 0.78
      1.00 → 1.00
    """
    if score <= 0:
        return 0.0
    return score ** power


# ╔══════════════════════════════════════════════════════════════╗
# ║           NOWE: METRYKI JAKOŚCI TEKSTU                       ║
# ╚══════════════════════════════════════════════════════════════╝

def _text_quality_score(text: str) -> float:
    """
    Ocena formalności/jakości tekstu (0.0 = byle jak, 1.0 = profesjonalny).

    Mierzy:
    1. Kapitalizacja na początku zdań
    2. Średnia długość słów (formalne = dłuższe)
    3. Różnorodność słownictwa (type-token ratio)
    4. Średnia długość zdań (formalne = dłuższe)
    5. Kompletność interpunkcji

    Wikipedia → ~0.85–0.95
    4chan      → ~0.15–0.40
    """
    if not text or not text.strip():
        return 0.5

    words = text.split()
    word_count = len(words)
    if word_count < 5:
        return 0.3  # zbyt mało tekstu — niska pewność, obniżamy

    # ── 1. Kapitalizacja zdań ──
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 2]

    if sentences:
        cap_starts = sum(1 for s in sentences if s[0].isupper())
        capitalization = cap_starts / len(sentences)
    else:
        capitalization = 0.3

    # ── 2. Średnia długość słów ──
    alpha_words = [w for w in words if w.isalpha()]
    if alpha_words:
        avg_word_len = sum(len(w) for w in alpha_words) / len(alpha_words)
        # formalny tekst: ~5.5+ znaków/słowo, nieformalny: ~3.5
        word_len_score = _saturate(avg_word_len - 2.5, 3.5)  # 2.5→0.0, 6.0→1.0
    else:
        word_len_score = 0.3

    # ── 3. Type-token ratio (różnorodność słownictwa) ──
    unique_lower = set(w.lower() for w in words)
    raw_ttr = len(unique_lower) / word_count

    # TTR naturalnie spada z długością tekstu — normalizujemy
    # Dla 100 słów dobry TTR > 0.6, dla 1000 słów > 0.35
    expected_ttr = 0.75 - 0.35 * min(word_count / 1000, 1.0)
    ttr_score = min(raw_ttr / max(expected_ttr, 0.1), 1.0)

    # ── 4. Średnia długość zdań ──
    if sentences:
        sent_lengths = [len(s.split()) for s in sentences if s.strip()]
        avg_sent_len = sum(sent_lengths) / len(sent_lengths) if sent_lengths else 0
    else:
        avg_sent_len = 0

    # formalny tekst: 12-25 słów/zdanie, posty forum: 3-8
    sent_len_score = _saturate(avg_sent_len, 18.0)

    # ── 5. Interpunkcja ──
    proper_endings = len(re.findall(r"[.!?]\s", text))
    if text.strip() and text.strip()[-1] in ".!?":
        proper_endings += 1

    expected_endings = max(len(sentences), 1)
    punct_score = min(proper_endings / expected_endings, 1.0)

    # ── 6. BONUS: procent małych liter na początku "zdań" (po newline) ──
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if lines:
        lowercase_starts = sum(
            1 for line in lines
            if line and line[0].islower()
        )
        lowercase_ratio = lowercase_starts / len(lines)
        no_caps_penalty = lowercase_ratio * 0.3  # max -0.3 za brak wielkich liter
    else:
        no_caps_penalty = 0.0

    # ── Łączenie ──
    quality = (
        capitalization * 0.20
        + word_len_score * 0.20
        + ttr_score * 0.15
        + sent_len_score * 0.25
        + punct_score * 0.20
        - no_caps_penalty
    )

    return round(max(0.0, min(1.0, quality)), 4)


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


def _clickbait_score(title: str, text_opening: str) -> float:
    combined = (title + " " + text_opening).lower()
    hits = _count_pattern_hits(combined, _RE_CLICKBAIT)
    return min(hits / 3.0, 1.0)


# ╔══════════════════════════════════════════════════════════════╗
# ║               WARSTWA 1 — ANALIZA REGUŁOWA                  ║
# ╚══════════════════════════════════════════════════════════════╝

def rule_based_analysis(text: str, title: str) -> tuple[RuleBasedScores, list[str], dict]:
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

    # ══════════════════════════════════════
    # WORD MATCHING
    # ══════════════════════════════════════

    vulgar_hits = _count_matches(text_lower, VULGAR_PL + VULGAR_EN)
    emotional_hits = _count_matches(text_lower, EMOTIONAL_PL + EMOTIONAL_EN)
    negative_hits = _count_matches(text_lower, NEGATIVE_PL + NEGATIVE_EN)
    speculative_hits = _count_matches(text_lower, SPECULATIVE_PL + SPECULATIVE_EN)
    conspiracy_hits = _count_matches(text_lower, CONSPIRACY_PL + CONSPIRACY_EN)
    informal_hits = _count_matches(text_lower, INFORMAL_EN + INFORMAL_PL)
    toxic_hits = _count_matches(text_lower, TOXIC_EN + TOXIC_PL)

    # Pattern-based
    aggressive_hits = _count_pattern_hits(text_lower, _RE_AGGRESSIVE)
    ugc_hits = _count_pattern_hits(text, _RE_UGC)

    # Title analysis
    title_vulgar = _count_matches(title_lower, VULGAR_PL + VULGAR_EN)
    title_emotional = _count_matches(title_lower, EMOTIONAL_PL + EMOTIONAL_EN)
    title_informal = _count_matches(title_lower, INFORMAL_EN + INFORMAL_PL)
    title_toxic = _count_matches(title_lower, TOXIC_EN + TOXIC_PL)

    # ══════════════════════════════════════
    # SCORING — dual (density + absolute)
    # ══════════════════════════════════════
    # Format: _dual_score(hits, per_100, density_ceiling, absolute_ceiling)
    # Niższe ceiling = wyższa czułość

    vulgarity_score = _dual_score(vulgar_hits, per_100, 1.5, 4)
    emotionality_score = _dual_score(emotional_hits, per_100, 3.0, 6)
    negativity_score = _dual_score(negative_hits, per_100, 3.0, 6)
    speculative_score = _dual_score(speculative_hits, per_100, 2.5, 5)
    conspiracy_score = _dual_score(conspiracy_hits, per_100, 2.0, 4)
    informal_score = _dual_score(informal_hits, per_100, 2.0, 5)
    toxic_score = _dual_score(toxic_hits, per_100, 1.0, 3)

    # Agresja (pattern-based)
    aggressive_score = _saturate(aggressive_hits, 2.0)

    # UGC signals (user-generated unmoderated content)
    ugc_score = _saturate(ugc_hits, 3.0)

    # ══════════════════════════════════════
    # TEXT QUALITY
    # ══════════════════════════════════════

    text_quality = _text_quality_score(text)

    # ══════════════════════════════════════
    # FORMATTING
    # ══════════════════════════════════════

    caps_ratio = _all_caps_ratio(text)
    caps_score = _saturate(caps_ratio, 0.08)  # obniżony próg (było 0.1)

    excl_dens = _exclamation_density(text)
    excl_score = _saturate(excl_dens, 2.0)  # obniżony (było 3.0)

    ell_dens = _ellipsis_density(text)
    ell_score = _saturate(ell_dens, 2.0)

    title_caps_flag = 1.0 if title.isupper() and len(title) > 10 else 0.0
    title_question_flag = 0.3 if _question_headline(title) else 0.0
    cb_score = _clickbait_score(title, text[:500])

    formatting_abuse = min(
        caps_score * 0.25
        + excl_score * 0.25
        + ell_score * 0.15
        + title_caps_flag * 0.15
        + title_question_flag * 0.1
        + ugc_score * 0.1,   # UGC patterns contribute to formatting
        1.0,
    )

    # ══════════════════════════════════════
    # COMPOSITE PER-AXIS SCORES
    # ══════════════════════════════════════

    # Tytuł wzmacnia body scores
    title_vulgar_boost = _saturate(title_vulgar, 2.0)
    title_emotional_boost = _saturate(title_emotional, 2.0)
    title_informal_boost = _saturate(title_informal, 2.0)
    title_toxic_boost = _saturate(title_toxic, 1.0)

    vulgarity_combined = min(
        vulgarity_score * 0.6
        + title_vulgar_boost * 0.2
        + toxic_score * 0.15        # toksyczność podnosi wulgarność
        + aggressive_score * 0.05,
        1.0,
    )

    toxicity_combined = min(
        toxic_score * 0.5
        + aggressive_score * 0.3
        + title_toxic_boost * 0.2,
        1.0,
    )

    emotionality_combined = min(
        emotionality_score * 0.4
        + title_emotional_boost * 0.2
        + cb_score * 0.2
        + formatting_abuse * 0.1
        + aggressive_score * 0.1,
        1.0,
    )

    informality_combined = min(
        informal_score * 0.5
        + title_informal_boost * 0.1
        + ugc_score * 0.2
        + (1.0 - text_quality) * 0.2,  # niska jakość → więcej nieformalności
        1.0,
    )

    # ══════════════════════════════════════
    # BUILD RESULT
    # ══════════════════════════════════════

    scores = RuleBasedScores(
        vulgarity=round(vulgarity_combined, 4),
        negativity=round(negativity_score, 4),
        emotionality=round(emotionality_combined, 4),
        speculativeness=round(speculative_score, 4),
        clickbait=round(cb_score, 4),
        conspiracy=round(conspiracy_score, 4),
        formatting_abuse=round(formatting_abuse, 4),
        informality=round(informality_combined, 4),
        toxicity=round(toxicity_combined, 4),
        text_quality=round(text_quality, 4),
    )

    # ══════════════════════════════════════
    # SIGNALS
    # ══════════════════════════════════════

    signals: list[str] = []

    if vulgarity_combined > 0.15:
        signals.append(f"Vulgar language detected ({vulgar_hits} hits)")
    if toxicity_combined > 0.1:
        signals.append(f"Toxic/aggressive language ({toxic_hits} toxic + {aggressive_hits} aggressive patterns)")
    if emotionality_combined > 0.2:
        signals.append(f"Elevated emotional language ({emotional_hits} markers)")
    if negativity_score > 0.2:
        signals.append(f"Negative tone ({negative_hits} markers)")
    if speculative_score > 0.15:
        signals.append(f"Speculative language ({speculative_hits} markers)")
    if conspiracy_score > 0.15:
        signals.append(f"Conspiracy-related language ({conspiracy_hits} markers)")
    if informality_combined > 0.15:
        signals.append(f"Informal/slang language ({informal_hits} markers)")
    if text_quality < 0.4:
        signals.append(f"Low text quality (score: {text_quality:.2f})")
    if cb_score > 0.3:
        signals.append("Clickbait-style headline or opening")
    if caps_score > 0.3:
        signals.append("Excessive ALL CAPS usage")
    if excl_score > 0.3:
        signals.append("High exclamation mark density")
    if ell_score > 0.3:
        signals.append("Frequent ellipsis usage")
    if title_caps_flag:
        signals.append("Title is entirely uppercase")
    if ugc_score > 0.3:
        signals.append(f"User-generated content patterns detected ({ugc_hits} patterns)")

    if not signals:
        signals.append("Language appears neutral and well-structured")

    # ══════════════════════════════════════
    # DETAILS
    # ══════════════════════════════════════

    details = {
        "word_count": word_count,
        "vulgar_hits": vulgar_hits,
        "emotional_hits": emotional_hits,
        "negative_hits": negative_hits,
        "speculative_hits": speculative_hits,
        "conspiracy_hits": conspiracy_hits,
        "informal_hits": informal_hits,
        "toxic_hits": toxic_hits,
        "aggressive_pattern_hits": aggressive_hits,
        "ugc_pattern_hits": ugc_hits,
        "text_quality": round(text_quality, 4),
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
    informality: float,
    toxicity: float,
    text_quality: float,
) -> int:
    """
    Oblicza language_trust (0–100). 100 = wiarygodny, 0 = podejrzany.

    Kary z amplifikacją (power=0.65):
      input 0.05 → efektywne 0.13  (słabe sygnały nadal odczuwalne)
      input 0.10 → efektywne 0.22
      input 0.30 → efektywne 0.46
      input 0.50 → efektywne 0.64
      input 1.00 → efektywne 1.00

    Maksymalna suma kar: ~155 → clamp do 100.
    """
    penalty = (
        _amplify(vulgarity) * 25
        + _amplify(toxicity) * 22
        + _amplify(negativity) * 10
        + _amplify(emotionality) * 22
        + _amplify(speculativeness) * 12
        + _amplify(conspiracy) * 18
        + _amplify(informality) * 15
        + clickbait * 8
        + formatting * 5
        + (1.0 - text_quality) * 10  # niska jakość = kara
    )

    trust = max(0, min(100, 100 - int(penalty)))
    return trust


# ╔══════════════════════════════════════════════════════════════╗
# ║                   GŁÓWNE FUNKCJE                             ║
# ╚══════════════════════════════════════════════════════════════╝

async def analyze_language(text: str, title: str = "") -> LanguageResult:
    """Pełna analiza: reguły + AI."""
    rule_scores, rule_signals, rule_details = rule_based_analysis(text, title)

    ai_scores = await _get_ai_scores(text, title)

    vulgarity = _combine_axis(
        rule_scores.vulgarity, ai_scores.vulgarity if ai_scores else None
    )
    negativity = _combine_axis(
        rule_scores.negativity, ai_scores.negativity if ai_scores else None
    )
    emotionality = _combine_axis(
        rule_scores.emotionality, ai_scores.emotionality if ai_scores else None
    )
    speculativeness = _combine_axis(
        rule_scores.speculativeness, ai_scores.speculativeness if ai_scores else None
    )

    language_trust = _compute_language_trust(
        vulgarity=vulgarity,
        negativity=negativity,
        emotionality=emotionality,
        speculativeness=speculativeness,
        conspiracy=rule_scores.conspiracy,
        clickbait=rule_scores.clickbait,
        formatting=rule_scores.formatting_abuse,
        informality=rule_scores.informality,
        toxicity=rule_scores.toxicity,
        text_quality=rule_scores.text_quality,
    )

    signals = list(rule_signals)
    if ai_scores and ai_scores.confidence < 0.5:
        signals.append("AI: niska pewność oceny — wynik może być nieprecyzyjny")

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
        informality=rule_scores.informality,
        toxicity=rule_scores.toxicity,
        text_quality=rule_scores.text_quality,
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