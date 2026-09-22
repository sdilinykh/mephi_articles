from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from hashlib import sha256
import re
import threading
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning
import urllib3

from src.collectors.records import CollectedArticle, CollectedAuthor, CollectedGrant
from src.parsers.affiliation import clean_affiliation, is_mephi_affiliation
from src.parsers.article import parse_article_xml
from src.parsers.authors import clean_author_name, extract_author_orcids_from_html, extract_orcid, is_valid_author_name
from src.parsers.funding import FUNDING_PARSER_VERSION, extract_funding_from_html, extract_funding_from_sections, funding_section_found_in_html, funding_section_found_in_sections


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MEPhI-Journals-Dashboard/0.1; +https://mephi.ru)",
    "Accept": "application/xml,text/xml,*/*;q=0.8",
    "Connection": "close",
}
RETRY_STATUSES = {429, 500, 502, 503, 504}
AFFILIATION_PARSER_VERSION = "html-citation-author-institution-v1"
OAI_MAX_WORKERS = 6
urllib3.disable_warnings(InsecureRequestWarning)

_local = threading.local()


def _session(insecure: bool = False) -> requests.Session:
    key = "insecure" if insecure else "secure"
    session = getattr(_local, key, None)
    if session is None:
        session = requests.Session()
        session.trust_env = False
        setattr(_local, key, session)
    return session


def collect_oai_articles(endpoint: str, max_records: int | None = None) -> list[CollectedArticle]:
    identifiers = _list_identifiers(endpoint, max_records=max_records)
    netloc = urlparse(endpoint).netloc
    total = len(identifiers)
    print(f"{netloc}: found {total} OAI identifiers", flush=True)

    progress_lock = threading.Lock()
    done = 0

    def fetch(identifier: str) -> CollectedArticle | None:
        nonlocal done
        item = _parse_oai_record(_get_record(endpoint, identifier))
        with progress_lock:
            done += 1
            if done == 1 or done % 25 == 0 or done == total:
                print(f"{netloc}: parsed {done}/{total} OAI records", flush=True)
        return item

    # Records are parsed independently and upserted by source_article_id, so the
    # concurrent order does not change the stored result — only the wall time.
    with ThreadPoolExecutor(max_workers=OAI_MAX_WORKERS) as executor:
        results = executor.map(fetch, identifiers)

    return [item for item in results if item is not None]


def _list_identifiers(endpoint: str, max_records: int | None = None) -> list[str]:
    identifiers: list[str] = []
    token: str | None = None

    while True:
        params = {"verb": "ListIdentifiers", "metadataPrefix": "oai_dc"} if not token else {
            "verb": "ListIdentifiers",
            "resumptionToken": token,
        }
        response = _get_with_retries(endpoint, params=params)
        soup = BeautifulSoup(response.text, "xml")

        for header in soup.find_all("header"):
            if header.get("status") == "deleted":
                continue
            identifier = _text(header, "identifier")
            if identifier:
                identifiers.append(identifier)
            if max_records is not None and len(identifiers) >= max_records:
                return identifiers

        token_node = soup.find("resumptionToken")
        token = token_node.get_text(strip=True) if token_node else None
        if not token:
            return identifiers
        time.sleep(0.5)


def _get_record(endpoint: str, identifier: str):
    response = _get_with_retries(endpoint, params={
        "verb": "GetRecord",
        "metadataPrefix": "oai_dc",
        "identifier": identifier,
    })
    soup = BeautifulSoup(response.text, "xml")
    record = soup.find("record")
    if not record:
        raise RuntimeError(f"OAI record not found for {identifier}")
    return record


def _parse_oai_record(record) -> CollectedArticle | None:
    if record.find("header", {"status": "deleted"}):
        return None

    titles = _texts(record, "dc:title")
    title = _choose_title(titles)
    identifiers = _texts(record, "dc:identifier")
    url = next((x for x in identifiers if x.startswith("http")), None)
    doi = _extract_doi(" ".join(identifiers))
    if not title or not url:
        return None

    source_article_id = _source_id_from_url(url) or _text(record, "identifier") or url
    pub_date = _parse_date(next(iter(_texts(record, "dc:date")), None))
    source = " ".join(_texts(record, "dc:source"))
    volume, issue, source_year = _parse_source(source)
    year = pub_date.year if pub_date else source_year
    descriptions = _texts(record, "dc:description")
    page_html = _article_page_html(url)
    xml = _article_jats_xml(url, page_html)
    parsed_xml = parse_article_xml(xml) if xml else None
    funding_hits = [CollectedGrant(**item) for item in parsed_xml["funding"]] if parsed_xml and parsed_xml["funding"] else [
        CollectedGrant(**hit.__dict__) for hit in _funding_hits(page_html, descriptions)
    ]
    funding_section_found = (
        parsed_xml["funding_section_found"]
        if parsed_xml
        else funding_section_found_in_html(page_html) or funding_section_found_in_sections(" ".join(descriptions))
    )
    authors = [CollectedAuthor(**item) for item in parsed_xml["authors"]] if parsed_xml and parsed_xml["authors"] else _authors_from_html_meta(page_html)
    if not authors:
        authors = [
            CollectedAuthor(name=clean_author_name(name), orcid=extract_orcid(name), author_order=index)
            for index, name in enumerate(_dedupe(_texts(record, "dc:creator")), start=1)
            if is_valid_author_name(name)
        ]

    author_payload = "|".join(
        f"{author.name}:{author.orcid or ''}:{author.affiliation_raw or ''}:{author.is_mephi}"
        for author in authors
    )
    payload = "|".join([
        FUNDING_PARSER_VERSION,
        AFFILIATION_PARSER_VERSION,
        "jats-xml" if parsed_xml else "html-oai",
        parsed_xml["title"] if parsed_xml else title,
        url,
        (parsed_xml["doi"] if parsed_xml else doi) or "",
        str((parsed_xml["publication_date"] if parsed_xml else pub_date) or ""),
        str((parsed_xml["volume"] if parsed_xml else volume) or ""),
        str((parsed_xml["issue"] if parsed_xml else issue) or ""),
        str(funding_section_found),
        " ".join(descriptions),
        author_payload,
    ])
    return CollectedArticle(
        source_article_id=source_article_id,
        title=(parsed_xml["title"] if parsed_xml else None) or title,
        url=url,
        doi=(parsed_xml["doi"] if parsed_xml else None) or doi,
        publication_date=(parsed_xml["publication_date"] if parsed_xml else None) or pub_date,
        year=(parsed_xml["year"] if parsed_xml else None) or year,
        volume=(parsed_xml["volume"] if parsed_xml else None) or volume,
        issue=(parsed_xml["issue"] if parsed_xml else None) or issue,
        funding_section_found=funding_section_found,
        content_hash=sha256(payload.encode("utf-8")).hexdigest(),
        authors=authors,
        grants=funding_hits,
    )


def _texts(node, name: str) -> list[str]:
    return [" ".join(x.get_text(" ", strip=True).split()) for x in node.find_all(name) if x.get_text(strip=True)]


def _text(node, name: str) -> str | None:
    item = node.find(name)
    return " ".join(item.get_text(" ", strip=True).split()) if item else None


def _choose_title(titles: list[str]) -> str | None:
    if not titles:
        return None
    return next((x for x in titles if re.search(r"[A-Za-z]", x)), titles[0])


def _extract_doi(value: str) -> str | None:
    match = re.search(r"\b10\.\d{4,9}/[^\s,;<>]+", value, re.I)
    return match.group(0).rstrip(".") if match else None


def _source_id_from_url(url: str) -> str | None:
    match = re.search(r"/article/view/(\d+)", url)
    if match:
        return match.group(1)
    path = urlparse(url).path.strip("/")
    return path or None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    match = re.match(r"(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", value)
    if not match:
        return None
    year, month, day = match.groups()
    try:
        return date(int(year), int(month or 1), int(day or 1))
    except ValueError:
        return None


def _parse_source(value: str) -> tuple[str | None, str | None, int | None]:
    volume = None
    issue = None
    year = None

    volume_match = re.search(r"(?:Том|Vol(?:ume)?\.?)\s*([0-9A-Za-zА-Яа-я.-]+)", value, re.I)
    if volume_match:
        volume = volume_match.group(1)

    issue_match = re.search(r"(?:№|No\.?|N)\s*([0-9A-Za-zА-Яа-я.-]+)", value, re.I)
    if issue_match:
        issue = issue_match.group(1)

    year_match = re.search(r"\((\d{4})\)", value)
    if year_match:
        year = int(year_match.group(1))

    return volume, issue, year


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.lower()
        if key not in seen:
            result.append(value)
            seen.add(key)
    return result


def _article_page_html(url: str) -> str | None:
    try:
        response = _get_with_retries(url, params={})
        return response.text
    except requests.RequestException:
        return None


def _article_jats_xml(url: str, page_html: str | None) -> str | None:
    candidates = _jats_xml_candidates(url, page_html)
    for candidate in candidates:
        try:
            response = _get_with_retries(candidate, params={}, timeout=8)
        except requests.RequestException:
            continue
        if _looks_like_jats(response.text):
            return response.text
    return None


def _jats_xml_candidates(url: str, page_html: str | None) -> list[str]:
    candidates: list[str] = []
    if page_html:
        soup = BeautifulSoup(page_html, "lxml")
        for link in soup.find_all("a", href=True):
            href = link.get("href") or ""
            text = " ".join(link.get_text(" ", strip=True).split()).lower()
            href_lower = href.lower()
            if ("jats" in href_lower or "jats" in text or "xml" in text) and "pdf" not in href_lower:
                absolute = urljoin(url, href)
                if absolute not in candidates:
                    candidates.append(absolute)

    parsed = urlparse(url)
    match = re.search(r"(?P<prefix>/[^?#]*/article)/view/(?P<article_id>\d+)", parsed.path)
    if "elpub.ru" in parsed.netloc and match:
        candidate = f"{parsed.scheme}://{parsed.netloc}{match.group('prefix')}/jats/{match.group('article_id')}"
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _looks_like_jats(text: str) -> bool:
    head = text[:2000].lower()
    return "<article" in head and ("<front" in text[:10000].lower() or "article-type" in head)


def _funding_hits(page_html: str | None, descriptions: list[str]):
    if page_html:
        page_hits = extract_funding_from_html(page_html)
        if page_hits:
            return page_hits

    return extract_funding_from_sections(" ".join(descriptions))


def _authors_from_html_meta(html: str | None) -> list[CollectedAuthor]:
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    orcids_by_name = extract_author_orcids_from_html(html)
    authors: list[CollectedAuthor] = []
    current: dict | None = None

    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        content = " ".join((meta.get("content") or "").split())
        if not content:
            continue

        if name == "citation_author":
            if current:
                authors.append(_collected_author_from_meta(current, len(authors) + 1, orcids_by_name))
            current = {"name": content, "affiliations": [], "orcid": None}
        elif name == "citation_author_institution" and current:
            affiliation = clean_affiliation(content)
            if affiliation:
                current["affiliations"].append(affiliation)
        elif name == "citation_author_orcid" and current:
            current["orcid"] = extract_orcid(content)

    if current:
        authors.append(_collected_author_from_meta(current, len(authors) + 1, orcids_by_name))

    return _dedupe_authors(authors)


def _collected_author_from_meta(item: dict, order: int, orcids_by_name: dict[str, str] | None = None) -> CollectedAuthor:
    affiliations = item.get("affiliations") or []
    affiliation_raw = clean_affiliation("; ".join(dict.fromkeys(affiliations))) or None
    author_name = clean_author_name(item["name"])
    return CollectedAuthor(
        name=author_name,
        orcid=item.get("orcid") or (orcids_by_name or {}).get(author_name or "") or extract_orcid(item["name"]),
        affiliation_raw=affiliation_raw,
        is_mephi=is_mephi_affiliation(affiliation_raw or ""),
        author_order=order,
    )


def _dedupe_authors(authors: list[CollectedAuthor]) -> list[CollectedAuthor]:
    result: list[CollectedAuthor] = []
    seen: set[str] = set()
    for author in authors:
        if not is_valid_author_name(author.name):
            continue
        key = author.name.lower()
        if key in seen:
            continue
        seen.add(key)
        author.author_order = len(result) + 1
        result.append(author)
    return result


def _get_with_retries(url: str, params: dict, timeout: tuple[int, int] = (5, 20)) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = _session().get(url, params=params, headers=HEADERS, timeout=timeout)
            if response.status_code not in RETRY_STATUSES:
                response.raise_for_status()
                return response
            response.raise_for_status()
        except requests.exceptions.SSLError as exc:
            last_error = exc
            try:
                response = _session(insecure=True).get(url, params=params, headers=HEADERS, timeout=timeout, verify=False)
                if response.status_code not in RETRY_STATUSES:
                    response.raise_for_status()
                    return response
                response.raise_for_status()
            except requests.RequestException as insecure_exc:
                last_error = insecure_exc
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
        except requests.RequestException as exc:
            last_error = exc
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))

    raise RuntimeError(f"unreachable retry state: {last_error}")
