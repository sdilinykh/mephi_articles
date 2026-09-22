from __future__ import annotations
from datetime import date
from bs4 import BeautifulSoup
from .funding import extract_funding, extract_funding_from_html, funding_section_found_in_html, has_support_or_equipment_text, is_funding_section_heading
from .affiliation import clean_affiliation, is_mephi_affiliation
from .authors import clean_author_name, is_valid_author_name

FUNDING_HEADINGS = {"funding", "финансирование"}
ACK_HEADINGS = {"acknowledgements", "acknowledgments", "acknowledgement", "acknowledgment", "благодарности"}

def _clean_heading(value: str | None) -> str:
    return " ".join((value or "").replace("\ufeff", "").split()).lower()

def _section_texts_from_xml(soup: BeautifulSoup) -> list[str]:
    texts: list[str] = []
    for sec in soup.find_all("sec"):
        title = _clean_heading(sec.find("title").get_text(" ", strip=True) if sec.find("title") else None)
        sec_type = _clean_heading(sec.get("sec-type"))
        if title in FUNDING_HEADINGS or sec_type in FUNDING_HEADINGS or is_funding_section_heading(title) or is_funding_section_heading(sec_type):
            texts.append(" ".join(sec.get_text(" ", strip=True).replace("\ufeff", "").split()))

    for ack in soup.find_all("ack"):
        text = " ".join(ack.get_text(" ", strip=True).replace("\ufeff", "").split())
        if has_support_or_equipment_text(text):
            texts.append(text)

    return texts

def _node_text(node) -> str | None:
    if not node:
        return None
    value = " ".join(node.get_text(" ", strip=True).replace("\ufeff", "").split())
    return value or None

def _first_text(soup: BeautifulSoup, name: str) -> str | None:
    return _node_text(soup.find(name))

def _publication_date(soup: BeautifulSoup) -> date | None:
    pub_date = soup.find("pub-date", {"pub-type": "epub"}) or soup.find("pub-date", {"pub-type": "collection"})
    if not pub_date:
        return None

    year = _node_text(pub_date.find("year"))
    month = _node_text(pub_date.find("month")) or "1"
    day = _node_text(pub_date.find("day")) or "1"
    if not year or not year.isdigit():
        return None

    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None

def _name_from_contrib(contrib) -> str | None:
    name = contrib.find("name")
    if not name:
        return None
    surname = _node_text(name.find("surname"))
    given = _node_text(name.find("given-names"))
    parts = [x for x in [surname, given] if x]
    return " ".join(parts) if parts else _node_text(name)

def _orcid_from_contrib(contrib) -> str | None:
    for contrib_id in contrib.find_all("contrib-id"):
        if (contrib_id.get("contrib-id-type") or "").lower() == "orcid":
            value = contrib_id.get_text(strip=True)
            return value.replace("https://orcid.org/", "").replace("http://orcid.org/", "") or None
    return None

def _affiliation_map(soup: BeautifulSoup) -> dict[str, str]:
    result: dict[str, str] = {}
    for index, aff in enumerate(soup.find_all("aff"), start=1):
        aff_id = aff.get("id") or f"aff-{index}"
        text = clean_affiliation(_node_text(aff))
        if aff_id and text:
            result[aff_id] = text
    return result

def _authors_from_xml(soup: BeautifulSoup) -> list[dict]:
    affiliations = _affiliation_map(soup)
    authors: list[dict] = []
    for index, contrib in enumerate(soup.find_all("contrib", {"contrib-type": "author"}), start=1):
        name = _name_from_contrib(contrib)
        if not is_valid_author_name(name):
            continue
        name = clean_author_name(name)
        aff_texts = []
        for xref in contrib.find_all("xref", {"ref-type": "aff"}):
            rid = xref.get("rid")
            if rid and rid in affiliations:
                aff_texts.append(affiliations[rid])
        affiliation_raw = "; ".join(dict.fromkeys(aff_texts)) or None
        authors.append({
            "name": name,
            "orcid": _orcid_from_contrib(contrib),
            "affiliation_raw": affiliation_raw,
            "is_mephi": is_mephi_affiliation(affiliation_raw or ""),
            "author_order": index,
        })
    return authors

def parse_article_html(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("h1")
    title = " ".join(title_tag.get_text(" ", strip=True).replace("\ufeff", "").split()) if title_tag else None

    funding = extract_funding_from_html(html)

    affiliation_texts = []
    for node in soup.find_all(string=lambda s: s and ("MEPhI" in s or "МИФИ" in s)):
        value = " ".join(node.parent.get_text(" ", strip=True).split())
        if value:
            affiliation_texts.append(value)

    return {
        "title": title,
        "funding": [x.__dict__ for x in funding],
        "funding_section_found": funding_section_found_in_html(html),
        "mephi_affiliations": sorted(set(x for x in affiliation_texts if is_mephi_affiliation(x))),
        "has_mephi_author": any(is_mephi_affiliation(x) for x in affiliation_texts),
    }

def parse_article_xml(xml: str) -> dict:
    soup = BeautifulSoup(xml, "xml")

    title_tag = soup.find("article-title")
    title = " ".join(title_tag.get_text(" ", strip=True).replace("\ufeff", "").split()) if title_tag else None

    doi = None
    doi_tag = soup.find("article-id", {"pub-id-type": "doi"})
    if doi_tag:
        doi = doi_tag.get_text(strip=True) or None

    publication_date = _publication_date(soup)
    year = publication_date.year if publication_date else None
    if year is None:
        collection_date = soup.find("pub-date", {"pub-type": "collection"})
        collection_year = _node_text(collection_date.find("year")) if collection_date else None
        year = int(collection_year) if collection_year and collection_year.isdigit() else None

    funding_texts = _section_texts_from_xml(soup)
    funding = extract_funding(" ".join(funding_texts))
    authors = _authors_from_xml(soup)

    full_text = soup.get_text(" ", strip=True)
    affiliation_texts = []
    for node in soup.find_all(string=lambda s: s and ("MEPhI" in s or "МИФИ" in s)):
        value = " ".join(node.parent.get_text(" ", strip=True).split())
        if value:
            affiliation_texts.append(value)

    return {
        "title": title,
        "doi": doi,
        "publication_date": publication_date,
        "year": year,
        "volume": _first_text(soup, "volume"),
        "issue": _first_text(soup, "issue"),
        "funding": [x.__dict__ for x in funding],
        "funding_section_found": bool(funding_texts),
        "funding_texts": funding_texts,
        "authors": authors,
        "mephi_affiliations": sorted(set(x for x in affiliation_texts if is_mephi_affiliation(x))),
        "has_mephi_author": any(x["is_mephi"] for x in authors) or any(is_mephi_affiliation(x) for x in affiliation_texts) or is_mephi_affiliation(full_text),
    }
