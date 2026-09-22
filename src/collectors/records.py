from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class CollectedAuthor:
    name: str
    orcid: str | None = None
    affiliation_raw: str | None = None
    is_mephi: bool = False
    author_order: int = 0


@dataclass
class CollectedGrant:
    funder_raw: str
    funder_normalized: str
    grant_number: str | None
    funding_text_raw: str


@dataclass
class CollectedArticle:
    source_article_id: str
    title: str
    url: str
    doi: str | None = None
    publication_date: date | None = None
    year: int | None = None
    volume: str | None = None
    issue: str | None = None
    funding_section_found: bool = False
    content_hash: str | None = None
    authors: list[CollectedAuthor] = field(default_factory=list)
    grants: list[CollectedGrant] = field(default_factory=list)
