from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from hashlib import sha256
import re

import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning
import urllib3

from src.collectors.records import CollectedArticle, CollectedAuthor, CollectedGrant
from src.parsers.article import parse_article_xml
from src.parsers.authors import clean_author_name, extract_orcid, is_valid_author_name
from src.parsers.funding import FUNDING_PARSER_VERSION, extract_funding_from_html, funding_section_found_in_html


RSS_URL = "https://nuclear-power-engineering.ru/index.xml"
HEADERS = {"User-Agent": "MEPhI-Journals-Dashboard/0.1 (academic metadata collector)"}
urllib3.disable_warnings(InsecureRequestWarning)


def _get(url: str, timeout: int) -> requests.Response:
    session = requests.Session()
    session.trust_env = False
    try:
        response = session.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.SSLError:
        session = requests.Session()
        session.trust_env = False
        response = session.get(url, headers=HEADERS, timeout=timeout, verify=False)
        response.raise_for_status()
        return response


def collect_articles(max_records: int | None = None) -> list[CollectedArticle]:
    response = _get(RSS_URL, timeout=60)
    soup = BeautifulSoup(response.text, "xml")
    articles: list[CollectedArticle] = []

    for item in soup.find_all("item"):
        link = _text(item, "link")
        title = _text(item, "title")
        if not link or not title or "/article/" not in link:
            continue

        page = _fetch_article_page(link)
        parsed_xml = page["xml"]
        pub_date = _parse_rss_date(_text(item, "pubDate"))
        year, issue = _year_issue_from_url(link)
        doi = (parsed_xml["doi"] if parsed_xml else None) or page["doi"]
        authors = [CollectedAuthor(**item) for item in parsed_xml["authors"]] if parsed_xml and parsed_xml["authors"] else [
            CollectedAuthor(name=clean_author_name(name), orcid=extract_orcid(name), author_order=index)
            for index, name in enumerate(page["authors"], start=1)
            if is_valid_author_name(name)
        ]
        grants = [CollectedGrant(**item) for item in parsed_xml["funding"]] if parsed_xml and parsed_xml["funding"] else [
            CollectedGrant(**hit.__dict__) for hit in extract_funding_from_html(page["html"])
        ]
        funding_section_found = parsed_xml["funding_section_found"] if parsed_xml else funding_section_found_in_html(page["html"])
        payload = "|".join([FUNDING_PARSER_VERSION, "jats-xml" if parsed_xml else "html", title, link, doi or "", str(pub_date or ""), str(funding_section_found), page["text"][:2000]])

        articles.append(CollectedArticle(
            source_article_id=link.rstrip("/").removeprefix("https://nuclear-power-engineering.ru/"),
            title=(parsed_xml["title"] if parsed_xml else None) or page["title"] or title,
            url=link,
            doi=doi,
            publication_date=(parsed_xml["publication_date"] if parsed_xml else None) or pub_date,
            year=(parsed_xml["year"] if parsed_xml else None) or year or (pub_date.year if pub_date else None),
            volume=parsed_xml["volume"] if parsed_xml else None,
            issue=(parsed_xml["issue"] if parsed_xml else None) or issue,
            funding_section_found=funding_section_found,
            content_hash=sha256(payload.encode("utf-8")).hexdigest(),
            authors=authors,
            grants=grants,
        ))

        if max_records is not None and len(articles) >= max_records:
            break

    return articles


def _fetch_article_page(url: str) -> dict:
    response = _get(url, timeout=30)
    soup = BeautifulSoup(response.text, "lxml")
    text = " ".join(soup.get_text(" ", strip=True).split())
    title_node = soup.find("h1")
    title = " ".join(title_node.get_text(" ", strip=True).split()) if title_node else None

    doi = None
    doi_link = soup.find("a", href=re.compile(r"doi\.org/10\.", re.I))
    if doi_link:
        match = re.search(r"10\.\d{4,9}/[^\s,;<>]+", doi_link.get("href", ""), re.I)
        doi = match.group(0).rstrip(".") if match else None

    authors = []
    for href in soup.find_all("a", href=re.compile(r"/authors/", re.I)):
        value = " ".join(href.get_text(" ", strip=True).split())
        if is_valid_author_name(value) and value not in authors:
            authors.append(value)

    return {"title": title, "doi": doi, "authors": authors, "text": text, "html": response.text, "xml": _article_jats_xml(url, soup)}


def _article_jats_xml(url: str, soup: BeautifulSoup) -> dict | None:
    for link in soup.find_all("a", href=True):
        href = link.get("href") or ""
        text = " ".join(link.get_text(" ", strip=True).split()).lower()
        if ("jats" not in href.lower() and "jats" not in text and "xml" not in text) or "pdf" in href.lower():
            continue
        try:
            response = _get(href if href.startswith("http") else requests.compat.urljoin(url, href), timeout=8)
        except requests.RequestException:
            continue
        if "<article" in response.text[:2000].lower():
            return parse_article_xml(response.text)
    return None


def _text(node, name: str) -> str | None:
    item = node.find(name)
    return item.get_text(" ", strip=True) if item else None


def _parse_rss_date(value: str | None):
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError):
        return None


def _year_issue_from_url(url: str) -> tuple[int | None, str | None]:
    match = re.search(r"/article/(\d{4})/(\d{2})/", url)
    if not match:
        return None, None
    return int(match.group(1)), str(int(match.group(2)))
