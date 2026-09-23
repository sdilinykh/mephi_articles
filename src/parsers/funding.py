from __future__ import annotations
from dataclasses import dataclass
import re
from bs4 import BeautifulSoup

FUNDING_PARSER_VERSION = "funding-sections-v6"

@dataclass
class FundingHit:
    funder_raw: str
    funder_normalized: str
    grant_number: str | None
    funding_text_raw: str

FUNDER_PATTERNS = [
    (re.compile(r"\b(?:RFBR|Russian Foundation for Basic Research)\b", re.I), "RFBR"),
    (re.compile(r"\b(?:RSF|Russian Science Foundation|Russian Scientific Foundation)\b", re.I), "RSF"),
    (re.compile(r"(?:РФФИ|Российск\w+\s+фонд\w*\s+фундаментальн\w+\s+исследован\w*)", re.I), "RFBR"),
    (re.compile(r"(?:РНФ|Российск\w+\s+научн\w+\s+фонд\w*)", re.I), "RSF"),
    (re.compile(r"Ministry of (?:Science and Higher Education|Education and Science) of the Russian Federation", re.I), "Ministry of Science and Higher Education of the Russian Federation"),
    (re.compile(r"Ministry of Education and Science of the Republic of Kazakhstan", re.I), "Ministry of Education and Science of Kazakhstan"),
    (re.compile(r"Ministry of Science\s*&\s*Technology\s*\(MOST\),?\s*Bangladesh", re.I), "MOST Bangladesh"),
    (re.compile(r"\b(?:National Research Nuclear University MEPhI|NRNU MEPhI|MEPhI Academic Excellence Project|MEPhI Competitiveness Improvement Program|Competitiveness Growth Program of the NRNU MEPhI)\b", re.I), "NRNU MEPhI"),
    (re.compile(r"\b(?:Priority 2030|TPU development programme Priority 2030)\b", re.I), "Priority 2030"),
    (re.compile(r"\bState Assignment\b", re.I), "State Assignment"),
    (re.compile(r"\b(?:State Corporation Rosatom|Rosatom)\b", re.I), "Rosatom"),
    (re.compile(r"\b(?:Horizon 2020|RAMONES|European Union[’']s Horizon 2020)\b", re.I), "Horizon 2020"),
    (re.compile(r"China Guangdong Nuclear Power Research Institute", re.I), "China Guangdong Nuclear Power Research Institute"),
    (re.compile(r"National Research Center Kurchatov Institute|NRC Kurchatov Institute", re.I), "NRC Kurchatov Institute"),
    (re.compile(r"Government of the Kaluga Region", re.I), "Government of the Kaluga Region"),
    (re.compile(r"Vladimir Potanin Foundation", re.I), "Vladimir Potanin Foundation"),
    (re.compile(r"U\.?S\.? Department of Energy|DOE-NERI|NEUP", re.I), "U.S. Department of Energy"),
    (re.compile(r"Near East University|University of Kyrenia", re.I), "Near East University / University of Kyrenia"),
    (re.compile(r"Nuclear Power Plants Authority\s*\(NPPA\)", re.I), "NPPA Egypt"),
    (re.compile(r"Military Technical College\s*\(MTC\)", re.I), "Military Technical College"),
    (re.compile(r"National Research and Innovation Agency\s*\(BRIN\)", re.I), "BRIN"),
    (re.compile(r"China Institute of Atomic Energy|CIAE", re.I), "China Institute of Atomic Energy"),
]

# Номер гранта в этой базе — числовой идентификатор. Разрешаем только цифры и
# разделители, но обязательно требуем хотя бы одну цифру. Это исключает слова,
# ошибочно захваченные после «N» внутри названия организации (Foundation → dation).
GRANT_NUMBER = r"(\d+(?:[./–—-]\d+)*)(?![A-ZА-Я0-9])"
# Вёрстка журналов иногда ставит сноску между словом «project» и номером.
# Сноска не входит в номер и должна быть пропущена до его извлечения.
GRANT_NUMBER_PREFIX = r"(?:[¹²³⁴⁵⁶⁷⁸⁹⁰*†‡]+\s*)?"
# Идентификатор без явной метки допускаем только с двумя и более
# разделителями: это отсекает годы и диапазоны дат, но покрывает форматы
# 19-11-110082 и 14.604.21.0178 после названия фонда.
UNLABELLED_GRANT_NUMBER = r"(?<![A-Za-zА-Яа-я0-9])(?<![A-Za-zА-Яа-я]-)(?<![A-Za-zА-Яа-я][./–—-])(?<![0-9][./–—-])(\d+(?:[./–—-]\d+){2,})(?![A-Za-zА-Яа-я0-9])"
IMMEDIATE_GRANT_NUMBER = r"^\s*(?:[¹²³⁴⁵⁶⁷⁸⁹⁰*†‡]+\s*)?(\d+(?:[./–—-]\d+)+)(?![A-Za-zА-Яа-я0-9])"
GRANT_PATTERNS = [
    re.compile(
        rf"\b(?:project|grant)(?:s|\s+(?:no\.?|number(?:s)?))?\s*[:№#]?\s*{GRANT_NUMBER_PREFIX}{GRANT_NUMBER}",
        re.I,
    ),
    re.compile(
        rf"\b(?:проект|грант)(?:а)?\s*(?:№|\b(?:N|No\.?)\b)?\s*{GRANT_NUMBER_PREFIX}{GRANT_NUMBER}",
        re.I,
    ),
    re.compile(rf"(?:№|#|\bN\.?|\bNo\.?)\s*{GRANT_NUMBER_PREFIX}{GRANT_NUMBER}", re.I),
    re.compile(rf"\b(?:Agreement|Contract|Order)(?:\s+No\.?)?\s*[:№#]?\s*{GRANT_NUMBER_PREFIX}{GRANT_NUMBER}", re.I),
    re.compile(rf"\bProject\s+ID\s*:\s*{GRANT_NUMBER_PREFIX}{GRANT_NUMBER}", re.I),
]

FUNDING_SECTION_HEADINGS = {
    "acknowledgement",
    "acknowledgements",
    "acknowledgment",
    "acknowledgments",
    "funding",
    "financial support",
    "funding information",
    "источник финансирования",
    "источники финансирования",
    "финансирование",
    "при поддержке",
    "благодарности",
}

SECTION_END_HEADINGS = {
    "abstract",
    "аннотация",
    "keywords",
    "ключевые слова",
    "introduction",
    "введение",
    "conclusion",
    "conclusions",
    "заключение",
    "references",
    "reference",
    "список литературы",
    "литература",
    "conflict of interest",
    "conflicts of interest",
    "конфликт интересов",
    "author contributions",
    "about the authors",
    "about authors",
    "об авторах",
    "received",
    "for citation",
}

SUPPORT_OR_EQUIPMENT_RE = re.compile(
    r"(?:"
    r"\b(?:supported|funded|financed|financial support|grant|project|agreement|contract)\b|"
    r"\b(?:equipment|facility|facilities|infrastructure|beamline|laborator(?:y|ies)|"
    r"comput(?:ing|ational)\s+resources?|supercomputer|measurements?\s+(?:were\s+)?(?:performed|carried out))\b|"
    r"\b(?:поддерж\w*|финансир\w*|грант\w*|проект\w*|соглашени\w*|договор\w*)\b|"
    r"\b(?:оборудован\w*|установк\w*|прибор\w*|инфраструктур\w*|лаборатор\w*|"
    r"ресурс\w*|вычислительн\w*|суперкомпьютер\w*|измерени\w*)\b|"
    r"центр\w*\s+коллективн\w*\s+пользован\w*|"
    r"работа\s+выполнен\w*|исследовани\w+\s+выполнен\w*|публикаци\w+\s+подготовлен\w*"
    r")",
    re.I,
)


def extract_funding(text: str) -> list[FundingHit]:
    clean = " ".join(text.split())
    hits: list[FundingHit] = []
    for pattern, normalized in FUNDER_PATTERNS:
        for match in pattern.finditer(clean):
            left = max(0, match.start() - 180)
            right = min(len(clean), match.end() + 220)
            context = clean[left:right]
            grant_number = _grant_number_near_funder(clean, match, normalized)
            hits.append(FundingHit(
                funder_raw=match.group(0),
                funder_normalized=normalized,
                grant_number=grant_number,
                funding_text_raw=context,
            ))
    # de-duplicate identical normalized funder + grant number pairs
    unique = {}
    for h in hits:
        unique[(h.funder_normalized, h.grant_number)] = h
    return list(unique.values())


def has_support_or_equipment_text(text: str | None) -> bool:
    return bool(text and SUPPORT_OR_EQUIPMENT_RE.search(" ".join(text.split())))


def _contains_other_funder(value: str, current_span_text: str, current_normalized: str) -> bool:
    for pattern, normalized in FUNDER_PATTERNS:
        for match in pattern.finditer(value):
            if match.group(0).lower() != current_span_text.lower() and normalized != current_normalized:
                return True
    return False


def _grant_number_near_funder(clean: str, funder_match: re.Match, current_normalized: str) -> str | None:
    current_funder = funder_match.group(0)

    right_context = clean[funder_match.end(): min(len(clean), funder_match.end() + 220)]
    for pattern in GRANT_PATTERNS:
        grant_match = pattern.search(right_context)
        if not grant_match:
            continue
        between = right_context[:grant_match.start()]
        if _contains_other_funder(between, current_funder, current_normalized):
            continue
        return grant_match.group(1).rstrip(".,;)")

    # A frequent wording is "Russian Science Foundation 19-11-110082":
    # the number has no explicit No./grant marker, but its structured numeric
    # form immediately after the funder distinguishes it from a year or date.
    right_number = re.search(UNLABELLED_GRANT_NUMBER, right_context)
    if right_number:
        between = right_context[:right_number.start()]
        if not _contains_other_funder(between, current_funder, current_normalized):
            return right_number.group(1).rstrip(".,;)")

    immediate_number = re.search(IMMEDIATE_GRANT_NUMBER, right_context)
    if immediate_number:
        return immediate_number.group(1).rstrip(".,;)")

    left_context = clean[max(0, funder_match.start() - 220): funder_match.start()]
    for pattern in GRANT_PATTERNS:
        matches = list(pattern.finditer(left_context))
        if not matches:
            continue
        grant_match = matches[-1]
        between = left_context[grant_match.end():]
        if _contains_other_funder(between, current_funder, current_normalized):
            continue
        return grant_match.group(1).rstrip(".,;)")

    left_number_matches = list(re.finditer(UNLABELLED_GRANT_NUMBER, left_context))
    if left_number_matches:
        grant_match = left_number_matches[-1]
        between = left_context[grant_match.end():]
        if not _contains_other_funder(between, current_funder, current_normalized):
            return grant_match.group(1).rstrip(".,;)")

    return None


def extract_funding_from_sections(text: str) -> list[FundingHit]:
    return extract_funding(" ".join(_funding_section_texts(text)))


def funding_section_found_in_sections(text: str) -> bool:
    return bool(_funding_section_texts(text))


def extract_funding_from_html(html: str) -> list[FundingHit]:
    soup = BeautifulSoup(html, "lxml")
    texts = _funding_section_texts_from_html(soup)
    if texts:
        return extract_funding(" ".join(texts))
    return []


def funding_section_found_in_html(html: str | None) -> bool:
    if not html:
        return False
    soup = BeautifulSoup(html, "lxml")
    return bool(_funding_section_texts_from_html(soup) or _funding_section_texts(soup.get_text(" ", strip=True)))


def _normalized_heading(value: str) -> str:
    clean = " ".join(value.replace("\ufeff", "").split()).strip(" .:;-–—").lower()
    return clean


def is_funding_section_heading(value: str | None) -> bool:
    if not value:
        return False
    return _normalized_heading(value) in FUNDING_SECTION_HEADINGS


def _is_section_end_heading(value: str) -> bool:
    heading = _normalized_heading(value)
    return heading in FUNDING_SECTION_HEADINGS or heading in SECTION_END_HEADINGS


def _funding_section_texts(text: str) -> list[str]:
    clean = " ".join(text.replace("\ufeff", "").split())
    if not clean:
        return []

    heading_pattern = re.compile(
        r"(?:^|[.!?]\s+)(?P<head>"
        r"acknowledgements?|acknowledgments?|funding information|financial support|funding|"
        r"источники финансирования|источник финансирования|финансирование|при поддержке|благодарности"
        r")\s*[:.\-–—]?\s+",
        re.I,
    )
    end_pattern = re.compile(
        r"(?:^|[.!?]\s+)(?:"
        r"abstract|аннотация|keywords|ключевые слова|introduction|введение|conclusions?|"
        r"заключение|references?|список литературы|литература|conflicts? of interest|"
        r"конфликт интересов|author contributions|about the authors|about authors|об авторах|"
        r"received|for citation"
        r")\s*[:.\-–—]?\s+",
        re.I,
    )
    texts: list[str] = []
    matches = list(heading_pattern.finditer(clean))
    for index, match in enumerate(matches):
        start = match.end()
        next_heading_start = matches[index + 1].start() if index + 1 < len(matches) else len(clean)
        end_match = end_pattern.search(clean, start, next_heading_start)
        end = end_match.start() if end_match else next_heading_start
        section = clean[start:end].strip()
        if section and SUPPORT_OR_EQUIPMENT_RE.search(section):
            texts.append(section)
    return texts


def _funding_section_texts_from_html(soup: BeautifulSoup) -> list[str]:
    heading_tags = ["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"]
    texts: list[str] = []

    for heading in soup.find_all(heading_tags):
        if not is_funding_section_heading(heading.get_text(" ", strip=True)):
            continue

        parts: list[str] = []
        for sibling in heading.find_all_next():
            if sibling is heading:
                continue
            if sibling.name in heading_tags and _is_section_end_heading(sibling.get_text(" ", strip=True)):
                break
            if sibling.find_parent(heading_tags) is not None:
                continue
            value = " ".join(sibling.get_text(" ", strip=True).split())
            if value:
                parts.append(value)
            if sibling.name in {"section", "div"} and parts:
                break

        section = " ".join(dict.fromkeys(parts))
        if section and SUPPORT_OR_EQUIPMENT_RE.search(section):
            texts.append(section)

    return texts
