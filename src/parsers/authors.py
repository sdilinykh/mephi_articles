from __future__ import annotations

import re

from bs4 import BeautifulSoup


EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
ORCID_RE = re.compile(r"\b(?:ORCID:?\s*)?(\d{4}-\d{4}-\d{4}-\d{3}[\dX])\b", re.I)
TRAILING_LABEL_RE = re.compile(r"\s+\d+(?:\s+ORCID:.*)?$", re.I)
AUTHOR_CHARS_RE = re.compile(r"[A-Za-zА-Яа-яЁё]")
INITIALS_FIRST_RE = re.compile(
    r"^(?P<initials>(?:(?:[A-ZА-ЯЁ]\.|[A-ZА-ЯЁ][a-zа-яё]{1,2}\.)\s*){1,3})\s+(?P<surname>[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё'’.-]+)$"
)
SURNAME_INITIALS_RE = re.compile(
    r"^(?P<surname>[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё'’.-]+)\s+(?P<initials>(?:(?:[A-ZА-ЯЁ]\.|[A-ZА-ЯЁ][a-zа-яё]{1,2}\.)\s*){1,3})$"
)
PLACE_ONLY_RE = re.compile(
    r"^(?:"
    r"india|germany|iraq|oman|algeria|spain|belarus|turkey|tanzania|costa rica|"
    r"republic of korea|saudi arabia|bulgaria|china|indonesia|morocco|usa|"
    r"novosibirsk|pushkin|tomsk|moscow|irkutsk|kirov|rabat(?: morocco)?|"
    r"saint[- ]petersburg|st[.]? petersburg"
    r")$",
    re.I,
)
BAD_AUTHOR_MARKERS = [
    "right column",
    "sources:",
    "co-authorship",
    "co-occurrence",
    "group",
    "llc",
    "jsc",
    "pjsc",
    "company",
    "enterprise",
    "university",
    "institute",
    "department",
    "laboratory",
    "center",
    "centre",
    "computing",
    "mstu",
    "ics ras",
    "street",
    "avenue",
    "shosse",
    "moscow",
    "russia",
]


def clean_author_name(value: str | None) -> str | None:
    if not value:
        return None
    name = " ".join(value.replace("\ufeff", " ").split())
    name = EMAIL_RE.sub("", name)
    name = re.sub(r"\b[\w.+-]+\s+@[\w.-]+\.\w+\b", "", name)
    name = ORCID_RE.sub("", name)
    name = TRAILING_LABEL_RE.sub("", name).strip(" ,;")
    name = normalize_author_name(name)
    return name or None


def normalize_author_name(value: str | None) -> str | None:
    if not value:
        return None
    name = " ".join(value.split()).strip(" ,;")
    if "," in name:
        surname, rest = name.split(",", 1)
        rest = " ".join(rest.split())
        return f"{surname.strip()}, {rest}".strip(" ,")

    match = INITIALS_FIRST_RE.match(name)
    if match:
        initials = " ".join(match.group("initials").replace(".", ". ").split())
        return f"{match.group('surname')}, {initials}"

    match = SURNAME_INITIALS_RE.match(name)
    if match:
        initials = " ".join(match.group("initials").replace(".", ". ").split())
        return f"{match.group('surname')}, {initials}"

    return name


def author_match_key(value: str | None) -> str | None:
    name = clean_author_name(value)
    if not name:
        return None
    return re.sub(r"[\W_]+", "", name, flags=re.UNICODE).casefold()


def extract_orcid(value: str | None) -> str | None:
    if not value:
        return None
    match = ORCID_RE.search(value)
    return match.group(1).upper() if match else None


def extract_author_orcids_from_html(html: str | None) -> dict[str, str]:
    if not html:
        return {}

    soup = BeautifulSoup(html, "lxml")
    result: dict[str, str] = {}

    for bio in soup.select(".authorBio"):
        name_node = bio.find("em")
        name = clean_author_name(name_node.get_text(" ", strip=True) if name_node else None)
        orcid = extract_orcid(" ".join(
            value
            for value in [
                bio.get_text(" ", strip=True),
                " ".join(a.get("href") or "" for a in bio.find_all("a")),
            ]
            if value
        ))
        if name and orcid:
            result.setdefault(name, orcid)

    current_name: str | None = None
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        content = " ".join((meta.get("content") or "").split())
        if not content:
            continue
        if name == "citation_author":
            current_name = clean_author_name(content)
        elif name == "citation_author_orcid" and current_name:
            orcid = extract_orcid(content)
            if orcid:
                result.setdefault(current_name, orcid)

    return result


def is_valid_author_name(value: str | None) -> bool:
    name = clean_author_name(value)
    if not name:
        return False
    lowered = name.lower()
    if len(name) < 3 or len(name) > 80:
        return False
    if not AUTHOR_CHARS_RE.search(name):
        return False
    if "@" in name or EMAIL_RE.search(name) or ORCID_RE.fullmatch(name):
        return False
    if PLACE_ONLY_RE.fullmatch(name):
        return False
    if re.fullmatch(r"[\W\d_]+", name):
        return False
    if re.fullmatch(r"\d+[\d\s-]*", name):
        return False
    if re.search(r"\d", name):
        return False
    if any(marker in lowered for marker in BAD_AUTHOR_MARKERS):
        return False
    return True
