from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy import select

from src.collectors.journals import MEPHI_JOURNALS, JournalSource
from src.collectors.nucet import collect_article_stubs, fetch_article_xml
from src.collectors.oai import collect_oai_articles
from src.collectors import nuclear_power, scientific_visualization
from src.collectors.records import CollectedArticle, CollectedAuthor, CollectedGrant
from src.db.database import SessionLocal, init_db, reset_db
from src.db.models import Article, ArticleAuthor, ArticleGrant, Author, Grant, Journal, JournalUpdateLog
from src.parsers.article import parse_article_xml
from src.parsers.funding import FUNDING_PARSER_VERSION


def seed_journals() -> dict[str, Journal]:
    with SessionLocal() as db:
        for source in MEPHI_JOURNALS:
            journal = db.scalar(select(Journal).where(Journal.source_key == source.source_key))
            if journal is None:
                journal = Journal(
                    source_key=source.source_key,
                    name=source.name,
                    url=source.url,
                    collector=source.collector,
                )
                db.add(journal)
            else:
                journal.name = source.name
                journal.url = source.url
                journal.collector = source.collector
        db.commit()
        return {j.source_key: j for j in db.scalars(select(Journal)).all()}


def _start_log(db, journal: Journal, status: str = "running") -> JournalUpdateLog:
    log = JournalUpdateLog(journal_id=journal.journal_id, status=status)
    db.add(log)
    db.flush()
    return log


def _finish_log(db, log: JournalUpdateLog, status: str, message: str | None = None) -> None:
    log.status = status
    log.message = message
    log.finished_at = datetime.now(timezone.utc)


def _get_or_create_author(db, item: dict) -> Author:
    author = db.scalar(
        select(Author).where(
            Author.name == item["name"],
            Author.orcid == item.get("orcid"),
        )
    )
    if author is None:
        author = Author(name=item["name"], orcid=item.get("orcid"))
        db.add(author)
        db.flush()
    return author


def _get_or_create_grant(db, item: dict) -> Grant:
    grant = db.scalar(
        select(Grant).where(
            Grant.funder_normalized == item["funder_normalized"],
            Grant.grant_number == item.get("grant_number"),
        )
    )
    if grant is None:
        grant = Grant(
            funder_normalized=item["funder_normalized"],
            grant_number=item.get("grant_number"),
        )
        db.add(grant)
        db.flush()
    return grant


def _sync_article(db, journal: Journal, item: CollectedArticle) -> bool:
    article = db.scalar(
        select(Article).where(
            Article.journal_id == journal.journal_id,
            Article.source_article_id == item.source_article_id,
        )
    )

    if article and item.content_hash and article.content_hash == item.content_hash:
        article.last_seen_at = datetime.now(timezone.utc)
        return False

    if article is None:
        article = Article(
            journal_id=journal.journal_id,
            source_article_id=item.source_article_id,
            title=item.title,
            url=item.url,
        )
        db.add(article)
        db.flush()
    else:
        db.query(ArticleAuthor).filter(ArticleAuthor.article_id == article.article_id).delete()
        db.query(ArticleGrant).filter(ArticleGrant.article_id == article.article_id).delete()

    article.title = item.title
    article.doi = item.doi
    article.publication_date = item.publication_date
    article.year = item.year
    article.volume = item.volume
    article.issue = item.issue
    article.funding_section_found = item.funding_section_found
    article.url = item.url
    article.content_hash = item.content_hash
    article.last_seen_at = datetime.now(timezone.utc)
    article.parsed_at = datetime.now(timezone.utc)

    linked_authors: set[int] = set()
    for author_item in item.authors:
        author = _get_or_create_author(db, author_item.__dict__)
        if author.author_id in linked_authors:
            continue
        linked_authors.add(author.author_id)
        db.add(ArticleAuthor(
            article_id=article.article_id,
            author_id=author.author_id,
            affiliation_raw=author_item.affiliation_raw,
            is_mephi=author_item.is_mephi,
            author_order=author_item.author_order,
        ))

    linked_grants: set[int] = set()
    for grant_item in item.grants:
        grant = _get_or_create_grant(db, grant_item.__dict__)
        if grant.grant_id in linked_grants:
            continue
        linked_grants.add(grant.grant_id)
        db.add(ArticleGrant(
            article_id=article.article_id,
            grant_id=grant.grant_id,
            funding_text_raw=grant_item.funding_text_raw,
            funder_raw=grant_item.funder_raw,
        ))

    return True


def _collected_from_nucet_stub(stub) -> CollectedArticle:
    xml, content_hash = fetch_article_xml(stub)
    parsed = parse_article_xml(xml)
    return CollectedArticle(
        source_article_id=stub.source_id,
        title=parsed["title"] or stub.title,
        url=stub.url,
        doi=parsed["doi"] or stub.doi,
        publication_date=parsed["publication_date"],
        year=parsed["year"],
        volume=parsed["volume"],
        issue=parsed["issue"],
        funding_section_found=parsed["funding_section_found"],
        content_hash=sha256(f"{FUNDING_PARSER_VERSION}:{content_hash}".encode("utf-8")).hexdigest(),
        authors=[CollectedAuthor(**item) for item in parsed["authors"]],
        grants=[CollectedGrant(**item) for item in parsed["funding"]],
    )


def update_nucet(max_pages: int | None = None) -> None:
    init_db()
    journals = seed_journals()
    journal = journals["nucet"]

    with SessionLocal() as db:
        log = _start_log(db, journal)
        log_id = log.log_id
        db.commit()

    pages_checked = 0
    articles_checked = 0
    articles_changed = 0
    page = 1

    try:
        while max_pages is None or page <= max_pages:
            stubs = collect_article_stubs(page=page)
            if not stubs:
                break

            pages_checked += 1
            with SessionLocal() as db:
                journal = db.scalar(select(Journal).where(Journal.source_key == "nucet"))
                log = db.get(JournalUpdateLog, log_id)

                for stub in stubs:
                    articles_checked += 1
                    if _sync_article(db, journal, _collected_from_nucet_stub(stub)):
                        articles_changed += 1
                    time.sleep(0.5)

                log.pages_checked = pages_checked
                log.articles_checked = articles_checked
                log.articles_changed = articles_changed
                db.commit()

            print(f"Page {page}: checked {len(stubs)} articles", flush=True)
            page += 1

        with SessionLocal() as db:
            log = db.get(JournalUpdateLog, log_id)
            _finish_log(db, log, "success", "NUCET update completed")
            log.pages_checked = pages_checked
            log.articles_checked = articles_checked
            log.articles_changed = articles_changed
            db.commit()

    except Exception as exc:
        with SessionLocal() as db:
            log = db.get(JournalUpdateLog, log_id)
            _finish_log(db, log, "failed", str(exc))
            log.pages_checked = pages_checked
            log.articles_checked = articles_checked
            log.articles_changed = articles_changed
            db.commit()
        raise


OAI_ENDPOINTS = {
    "bit": "https://bit.spels.ru/index.php/bit/oai",
    "vestnik_mephi": "https://vestnikmephi.elpub.ru/jour/oai",
    "global_nuclear_safety": "https://glonucsec.elpub.ru/jour/oai",
    "nuclear_physics_engineering": "https://npe.elpub.ru/jour/oai",
}


def _collect_for_source(source: JournalSource, max_records: int | None = None) -> list[CollectedArticle]:
    if source.source_key in OAI_ENDPOINTS:
        return collect_oai_articles(OAI_ENDPOINTS[source.source_key], max_records=max_records)
    if source.source_key == "nuclear_power_engineering":
        return nuclear_power.collect_articles(max_records=max_records)
    if source.source_key == "scientific_visualization":
        return scientific_visualization.collect_articles(max_records=max_records)
    raise NotImplementedError(f"Collector is not implemented for {source.source_key}")


def update_generic_source(source: JournalSource, max_records: int | None = None) -> None:
    journals = seed_journals()
    journal = journals[source.source_key]

    with SessionLocal() as db:
        log = _start_log(db, journal)
        log_id = log.log_id
        db.commit()

    articles_checked = 0
    articles_changed = 0
    try:
        collected = _collect_for_source(source, max_records=max_records)
        with SessionLocal() as db:
            journal = db.scalar(select(Journal).where(Journal.source_key == source.source_key))
            log = db.get(JournalUpdateLog, log_id)
            for item in collected:
                articles_checked += 1
                if _sync_article(db, journal, item):
                    articles_changed += 1
            log.pages_checked = 1
            log.articles_checked = articles_checked
            log.articles_changed = articles_changed
            _finish_log(db, log, "success", f"{source.name} update completed")
            db.commit()
        print(f"{source.source_key}: checked {articles_checked} articles", flush=True)
    except Exception as exc:
        with SessionLocal() as db:
            log = db.get(JournalUpdateLog, log_id)
            log.articles_checked = articles_checked
            log.articles_changed = articles_changed
            _finish_log(db, log, "failed", str(exc))
            db.commit()
        raise


def run(page: int = 1):
    update_nucet(max_pages=page)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop and recreate local database tables before updating")
    parser.add_argument("--all", action="store_true", help="Update all supported journals and log unsupported journals")
    parser.add_argument("--source", choices=[source.source_key for source in MEPHI_JOURNALS], help="Update one journal by source key")
    parser.add_argument("--max-pages", type=int, default=None, help="Limit NUCET pages for a quick run")
    parser.add_argument("--max-records", type=int, default=None, help="Limit non-NUCET records per journal for a quick run")
    args = parser.parse_args()

    if args.reset:
        reset_db()
    else:
        init_db()

    seed_journals()
    if args.source:
        source = next(source for source in MEPHI_JOURNALS if source.source_key == args.source)
        if source.source_key == "nucet":
            update_nucet(max_pages=args.max_pages)
        else:
            update_generic_source(source, max_records=args.max_records)
    elif args.all:
        update_nucet(max_pages=args.max_pages)
        for source in MEPHI_JOURNALS:
            if source.source_key == "nucet":
                continue
            try:
                update_generic_source(source, max_records=args.max_records)
            except Exception as exc:
                print(f"{source.source_key}: failed: {exc}")
    else:
        update_nucet(max_pages=args.max_pages or 1)


if __name__ == "__main__":
    main()
