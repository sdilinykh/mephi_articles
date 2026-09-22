import html
import re

AFFILIATION_LABEL = re.compile(r"^\s*\d+\s*[\).]?\s*")
ADDRESS_SEGMENT = re.compile(
    r"(?:"
    r"\b\d{5,6}\b|\b\d+[a-z]?\b|"
    r"\b(?:str|st|street|ave|avenue|shosse|highway|hwy|proyezd|prospect|pr|"
    r"sq|square|bldg|building|block|room|rooms|pob|p[.]o[.] box|po box|"
    r"post office box|lenin|leninsky|kashirskoye|ordzhonikidze|ferganskaya|"
    r"burnakovsky|mira|korolev|koroleva|profsoyuznaya|kievskoye|kiyevskoye)"
    r"\b)"
    r"|(?:ул[.]?|улица|проспект|шоссе|дом|корпус)",
    re.I,
)
PLACE_AFFILIATION_ONLY = re.compile(
    r"^(?:"
    r"obninsk|moscow|tomsk|dimitrovgrad|zarechny|nizhny novgorod|st[.]? peterburg|"
    r"saint[- ]petersburg|yekaterinburg|novovoronezh|ivanovo|beijing|athens|"
    r"russia|russian federation|obninsk russia|moscow russia|tomsk russia|"
    r"dimitrovgrad russia|zarechny russia|nizhny novgorod russia|"
    r"st[.]? peterburg russia|yekaterinburg russia|beijing china|athens greece"
    r")$",
    re.I,
)

AFFILIATION_NORMALIZERS = [
    (
        re.compile(r"\b(?:IATE|Obninsk Institute for Nuclear Power Engineering).*?(?:MEPhI|МИФИ)", re.I),
        "IATE MEPhI",
    ),
    (
        re.compile(r"\b(?:INPhE\s+MEPhI|MEPhI|MIFI|NRNU\s+MEPhI|National Research Nuclear University\s+MEPhI|Moscow Engineering Physics Institute|НИЯУ\s+МИФИ|Национальн\w+\s+исследовательск\w+\s+ядерн\w+\s+университет\w*\s+[«\"“”]?МИФИ)", re.I),
        "National Research Nuclear University MEPhI",
    ),
    (
        re.compile(r"\b(?:IPPE|Leypunsky|Leipunsky|Лейпунск)", re.I),
        'JSC "SSC RF-IPPE n.a. A.I. Leypunsky"',
    ),
    (
        re.compile(r"\b(?:VNIINM|Bochvar)", re.I),
        "A.A. Bochvar High-technology Research Institute of Inorganic Materials",
    ),
    (
        re.compile(r"\b(?:Kurchatov Institute|Курчатовск)", re.I),
        'National Research Center "Kurchatov Institute"',
    ),
    (
        re.compile(r"\b(?:NIKIET|Dollezhal)", re.I),
        "NIKIET JSC",
    ),
    (
        re.compile(r"\b(?:IBRAE|Nuclear Safety Institute)", re.I),
        "Nuclear Safety Institute of the Russian Academy of Sciences",
    ),
    (
        re.compile(r"\b(?:Karpov|NRFChI)", re.I),
        "Karpov Institute of Physical Chemistry",
    ),
    (
        re.compile(r"\b(?:OKB\s+[\"“”]?Gidropress|Gidropress)", re.I),
        "OKB Gidropress JSC",
    ),
    (
        re.compile(r"\b(?:Khlopin Radium Institute|V[.]?G[.]?\s+Khlopin)", re.I),
        "V.G. Khlopin Radium Institute JSC",
    ),
    (
        re.compile(r"\b(?:Sosny|AO Sosny)", re.I),
        "Sosny R&D Company",
    ),
    (
        re.compile(r"\bSkolkovo Institute of Science and Technology\b", re.I),
        "Skolkovo Institute of Science and Technology",
    ),
    (
        re.compile(r"\b(?:Moscow Power Engineering Institute|NRU\s+MPEI|National Research University\s+[\"“”]?Moscow Power Engineering Institute)", re.I),
        "National Research University Moscow Power Engineering Institute",
    ),
    (
        re.compile(r"\b(?:Budker Institute of Nuclear Physics|BINP)\b", re.I),
        "Budker Institute of Nuclear Physics SB RAS",
    ),
    (
        re.compile(r"\b(?:VNIITF|Zababakhin|All-Russian Research Center\s*[(]?VNIITF)", re.I),
        "Russian Federal Nuclear Center - Zababakhin All-Russia Research Institute of Technical Physics",
    ),
    (
        re.compile(r"\b(?:Debre Markos University|Collage of Natural and Computational Science|College of Natural and Computational Science)", re.I),
        "Debre Markos University",
    ),
    (
        re.compile(r"\bIbn Tofail University\b", re.I),
        "Ibn Tofail University",
    ),
    (
        re.compile(r"\bUniversity of Fallujah\b", re.I),
        "University of Fallujah",
    ),
    (
        re.compile(r"\b(?:Moscow State University of Civil Engineering|MSUCE)", re.I),
        "National Research Moscow State University of Civil Engineering",
    ),
    (
        re.compile(r"\b(?:Scientific and Technical Center Diaprom|STC Diaprom|Diaprom)", re.I),
        "JSC Scientific and Technical Center Diaprom",
    ),
    (
        re.compile(r"\bFGBUN Interdepartmental Center (?:for|of) Analytical Research", re.I),
        "FGBUN Interdepartmental Center for Analytical Research in the Field of Physics, Chemistry and Biology under the Presidium of the Russian Academy of Sciences",
    ),
    (
        re.compile(r"\bMoscow Institute of Physics and Technology|\bМосковский физико-технический институт", re.I),
        "Moscow Institute of Physics and Technology",
    ),
    (
        re.compile(r"\bAtomenergoproekt", re.I),
        "Atomenergoproekt JSC",
    ),
    (
        re.compile(r"\bKaluga Branch of (?:the )?(?:Bauman|Moscow State Technical)", re.I),
        "Kaluga Branch of Bauman Moscow State Technical University",
    ),
    (
        re.compile(r"\b(?:Bauman Moscow State Technical University|N[.]?E[.]?\s+Bauman|Moscow State Technical University n[.]?a[.]?\s+N[.]?E[.]?\s+Bauman)", re.I),
        "Bauman Moscow State Technical University",
    ),
    (
        re.compile(r"\b(?:Afrikantov OKBM|Afrikantov OKB Mechanical Engineering)", re.I),
        "Afrikantov OKBM JSC",
    ),
    (
        re.compile(r"\b(?:VNIIAES|All-Russian Research Institute (?:for|of) (?:Nuclear Power Plant|Nuclear Power Plants )?Operation|All-Russian Research Institute for Operation of Nuclear Power Plants)", re.I),
        "VNIIAES JSC",
    ),
    (
        re.compile(r"\bBeloyarsk NPP\b", re.I),
        "Beloyarsk NPP",
    ),
    (
        re.compile(r"\b(?:Beloyarsk AtomEnergoRepair|BelAER)\b", re.I),
        "Beloyarsk AtomEnergoRepair",
    ),
    (
        re.compile(r"\bUral Federal University\b", re.I),
        "Ural Federal University",
    ),
    (
        re.compile(r"\bNizhny Novgorod State Technical University", re.I),
        "Nizhny Novgorod State Technical University n.a. R.E. Alekseev",
    ),
    (
        re.compile(r"\b(?:JSC\s+[\"“”]?Proryv|Proryv\s+JSC|Proryv|Прорыв)\b", re.I),
        'JSC "Proryv"',
    ),
    (
        re.compile(r"\bNational Research Tomsk Polytechnic University|\bTomsk Polytechnic University", re.I),
        "National Research Tomsk Polytechnic University",
    ),
    (
        re.compile(r"\bCNIITMASH\b", re.I),
        'JSC RPA "CNIITMASH"',
    ),
    (
        re.compile(r"\b(?:State Atomic Energy Corporation\s+ROSATOM|ROSATOM\s+State Atomic Energy Corporation|State Corporation\s+[\"“”]?Rosatom|State corporation\s+[\"“”]?Rosatom)\b", re.I),
        "ROSATOM State Atomic Energy Corporation",
    ),
    (
        re.compile(r"\bFSUE\s+VNIIA\b", re.I),
        "FSUE VNIIA",
    ),
    (
        re.compile(r"\bRosenergoatom", re.I),
        'JSC "Rosenergoatom Concern"',
    ),
    (
        re.compile(r"\bRIAR\b|Research Institute of Atomic Reactors", re.I),
        "RIAR JSC",
    ),
]

MEPHI_PATTERNS = [
    re.compile(r"\bMEPhI\b", re.I),
    re.compile(r"\bMIFI\b", re.I),
    re.compile(r"\bNRNU\s+MEPhI\b", re.I),
    re.compile(r"\bNational Research Nuclear University\s+[\"“”']?MEPhI", re.I),
    re.compile(r"\bMoscow Engineering Physics Institute\b", re.I),
    re.compile(r"\bНИЯУ\s+МИФИ\b", re.I),
    re.compile(r"\bМИФИ\b", re.I),
    re.compile(r"Национальн\w+\s+исследовательск\w+\s+ядерн\w+\s+университет\w*\s+[«\"“”]?МИФИ", re.I),
]

def is_mephi_affiliation(text: str) -> bool:
    return any(p.search(text) for p in MEPHI_PATTERNS)


def _strip_address(value: str) -> str:
    parts = [part.strip(" ,") for part in value.split(",") if part.strip(" ,")]
    if len(parts) < 2:
        return value

    kept: list[str] = []
    for part in parts:
        if kept and ADDRESS_SEGMENT.search(part):
            break
        kept.append(part)

    if kept and len(kept) < len(parts):
        return ", ".join(kept)
    return value


def clean_affiliation(text: str | None) -> str | None:
    if not text:
        return None
    value = " ".join(html.unescape(text).split())
    value = AFFILIATION_LABEL.sub("", value)
    value = value.replace("&ldquo;", "“").replace("&rdquo;", "”").replace("&quot;", '"')
    if PLACE_AFFILIATION_ONLY.fullmatch(value):
        return None
    for pattern, normalized in AFFILIATION_NORMALIZERS:
        if pattern.search(value):
            return normalized
    value = _strip_address(value)
    return value or None
