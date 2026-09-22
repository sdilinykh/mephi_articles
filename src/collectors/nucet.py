from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Iterable
import json
import re
import threading
import time

import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning
import urllib3

BASE_URL = "https://nucet.pensoft.net"
BROWSE_URL = f"{BASE_URL}/browse_journal_articles.php"
HEADERS = {
    "User-Agent": "MEPhI-Journals-Dashboard/0.1 (academic metadata collector)"
}
RETRY_STATUSES = {429, 500, 502, 503, 504}
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

@dataclass
class ArticleStub:
    source: str
    source_id: str
    title: str
    doi: str | None
    url: str
    published_at: str | None = None

def _article_id_from_url(url: str) -> str | None:
    m = re.search(r"/article/(\d+)", url)
    return m.group(1) if m else None

def collect_article_stubs(page: int = 1) -> list[ArticleStub]:
    params = {
        "journal_id": 79,
        "journal_name": "nucet",
        "lang": "en",
        "p": page,
    }
    response = _get_with_retries(BROWSE_URL, params=params)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    results: list[ArticleStub] = []
    seen: set[str] = set()

    # Pensoft exposes article links on browse pages. We intentionally keep
    # discovery separate from article parsing so the source can be adapted
    # without touching funding/affiliation logic.
    for a in soup.select('a[href*="/article/"]'):
        href = a.get("href", "")
        if not href:
            continue
        url = requests.compat.urljoin(BASE_URL, href)
        source_id = _article_id_from_url(url)
        if not source_id or source_id in seen:
            continue
        title = " ".join(a.get_text(" ", strip=True).split())
        if not title:
            continue

        container = a.find_parent(["article", "div", "li"]) or a.parent
        text = " ".join(container.get_text(" ", strip=True).split()) if container else ""
        doi_match = re.search(r"10\.3897/nucet\.\d+\.\d+", text, re.I)
        date_match = re.search(r"\b\d{2}-\d{2}-\d{4}\b", text)

        results.append(ArticleStub(
            source="nucet",
            source_id=source_id,
            title=title,
            doi=doi_match.group(0) if doi_match else None,
            url=f"{BASE_URL}/article/{source_id}/",
            published_at=date_match.group(0) if date_match else None,
        ))
        seen.add(source_id)

    return results

def fetch_article_html(article: ArticleStub) -> tuple[str, str]:
    response = _get_with_retries(article.url, timeout=15)
    return response.text, sha256(response.content).hexdigest()

def fetch_article_xml(article: ArticleStub) -> tuple[str, str]:
    url = f"{BASE_URL}/article/{article.source_id}/download/xml/"
    response = _get_with_retries(url, timeout=15)
    return response.text, sha256(response.content).hexdigest()

def _get_with_retries(url: str, params: dict | None = None, timeout: int = 30) -> requests.Response:
    for attempt in range(4):
        try:
            response = _session().get(url, params=params, headers=HEADERS, timeout=timeout)
            if response.status_code not in RETRY_STATUSES:
                response.raise_for_status()
                return response
            response.raise_for_status()
        except requests.exceptions.SSLError:
            response = _session(insecure=True).get(url, params=params, headers=HEADERS, timeout=timeout, verify=False)
            if response.status_code not in RETRY_STATUSES:
                response.raise_for_status()
                return response
            response.raise_for_status()
        except requests.RequestException:
            if attempt == 3:
                raise

        retry_after = response.headers.get("Retry-After") if "response" in locals() else None
        delay = int(retry_after) if retry_after and retry_after.isdigit() else 15 * (attempt + 1)
        time.sleep(delay)

    raise RuntimeError("unreachable")

def save_stubs(stubs: Iterable[ArticleStub], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(x) for x in stubs], f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    stubs = collect_article_stubs(page=1)
    print(f"Found {len(stubs)} article stubs")
    for item in stubs[:5]:
        print(asdict(item))
