from __future__ import annotations

from datetime import date
from hashlib import sha256
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.collectors.records import CollectedArticle, CollectedAuthor, CollectedGrant
from src.parsers.article import parse_article_xml
from src.parsers.authors import clean_author_name, extract_orcid, is_valid_author_name
from src.parsers.funding import FUNDING_PARSER_VERSION, extract_funding_from_html, funding_section_found_in_html


BASE_URL = "https://sv-journal.org"
ISSUES_URL = f"{BASE_URL}/issues.php?lang=en"
HEADERS = {"User-Agent": "MEPhI-Journals-Dashboard/0.1 (academic metadata collector)"}


def collect_articles(max_records: int | None = None) -> list[CollectedArticle]:
    issue_urls = _issue_urls()
    articles: list[CollectedArticle] = []

    for issue_url in issue_urls:
        year, issue = _year_issue_from_url(issue_url)
        response = requests.get(issue_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser", from_encoding="windows-1251")

        for link, fallback_title, fallback_authors in _article_links(soup, issue_url):
            item = _parse_article(link, year=year, issue=issue, fallback_title=fallback_title, fallback_authors=fallback_authors)
            if item:
                articles.append(item)
            if max_records is not None and len(articles) >= max_records:
                return articles

    return articles


def _issue_urls() -> list[str]:
    response = requests.get(ISSUES_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser", from_encoding="windows-1251")
    urls: list[str] = []
    for a in soup.find_all("a", href=True):
        if "Issue contents" not in a.get_text(" ", strip=True):
            continue
        urls.append(urljoin(ISSUES_URL, a["href"]))
    return urls


def _article_links(soup: BeautifulSoup, issue_url: str) -> list[tuple[str, str, list[str]]]:
    result: list[tuple[str, str, list[str]]] = []
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        href = "".join(a["href"].split())
        if re.fullmatch(r"\d{2}/?", href) and len(text) > 20:
            parent_text = " ".join(a.parent.get_text(" ", strip=True).split())
            author_text = parent_text.replace(text, "", 1).strip()
            result.append((urljoin(issue_url, href), text, _split_authors(author_text)))
    return result


def _parse_article(
    url: str,
    year: int | None,
    issue: str | None,
    fallback_title: str,
    fallback_authors: list[str],
) -> CollectedArticle | None:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser", from_encoding="windows-1251")
    text = " ".join(soup.get_text(" ", strip=True).split())
    parsed_xml = _article_jats_xml(url, soup)

    title = (parsed_xml["title"] if parsed_xml else None) or _title(soup)
    if not title or title.lower() in {"scientific visualization", "main page"}:
        title = fallback_title
    if not title:
        return None
    doi = (parsed_xml["doi"] if parsed_xml else None) or _doi(text)
    authors = [CollectedAuthor(**item) for item in parsed_xml["authors"]] if parsed_xml and parsed_xml["authors"] else [
        CollectedAuthor(name=clean_author_name(name), orcid=extract_orcid(name), author_order=index)
        for index, name in enumerate(_authors(soup) or fallback_authors, start=1)
        if is_valid_author_name(name)
    ]
    grants = [CollectedGrant(**item) for item in parsed_xml["funding"]] if parsed_xml and parsed_xml["funding"] else [
        CollectedGrant(**hit.__dict__) for hit in extract_funding_from_html(response.text)
    ]
    funding_section_found = parsed_xml["funding_section_found"] if parsed_xml else funding_section_found_in_html(response.text)
    payload = "|".join([FUNDING_PARSER_VERSION, "jats-xml" if parsed_xml else "html", title, url, doi or "", str(funding_section_found), text[:2000]])

    return CollectedArticle(
        source_article_id=url.removeprefix(BASE_URL).strip("/"),
        title=title,
        url=url,
        doi=doi,
        publication_date=(parsed_xml["publication_date"] if parsed_xml else None) or (date(year, 1, 1) if year else None),
        year=(parsed_xml["year"] if parsed_xml else None) or year,
        volume=parsed_xml["volume"] if parsed_xml else None,
        issue=(parsed_xml["issue"] if parsed_xml else None) or issue,
        funding_section_found=funding_section_found,
        content_hash=sha256(payload.encode("utf-8")).hexdigest(),
        authors=authors,
        grants=grants,
    )


def _title(soup: BeautifulSoup) -> str | None:
    h1 = soup.find("h1")
    if h1:
        return " ".join(h1.get_text(" ", strip=True).split())
    title = soup.find("title")
    if not title:
        return None
    value = " ".join(title.get_text(" ", strip=True).split())
    return re.sub(r"\s*-\s*Scientific Visualization.*$", "", value).strip() or value


def _authors(soup: BeautifulSoup) -> list[str]:
    text = " ".join(soup.get_text(" ", strip=True).split())
    match = re.search(r"(?:Authors?|Авторы)\s*[:：]\s*(.+?)(?:Abstract|Аннотация|Keywords|Ключевые слова|DOI|$)", text, re.I)
    if not match:
        return []
    raw = match.group(1)
    return _split_authors(raw)


def _split_authors(raw: str) -> list[str]:
    parts = re.split(r"\s*,\s*|\s+;\s*", raw)
    return [x.strip() for x in parts if is_valid_author_name(x)][:20]


def _doi(text: str) -> str | None:
    match = re.search(r"\b10\.\d{4,9}/[^\s,;<>]+", text, re.I)
    return match.group(0).rstrip(".") if match else None


def _article_jats_xml(url: str, soup: BeautifulSoup) -> dict | None:
    for link in soup.find_all("a", href=True):
        href = link.get("href") or ""
        text = " ".join(link.get_text(" ", strip=True).split()).lower()
        if ("jats" not in href.lower() and "jats" not in text and "xml" not in text) or "pdf" in href.lower():
            continue
        try:
            response = requests.get(urljoin(url, href), headers=HEADERS, timeout=8)
            response.raise_for_status()
        except requests.RequestException:
            continue
        if "<article" in response.text[:2000].lower():
            return parse_article_xml(response.text)
    return None


def _year_issue_from_url(url: str) -> tuple[int | None, str | None]:
    match = re.search(r"/(\d{4})-(\d+)/", url)
    if not match:
        return None, None
    return int(match.group(1)), match.group(2)
