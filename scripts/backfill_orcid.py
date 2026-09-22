from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from sqlalchemy import create_engine, text

from src.parsers.authors import author_match_key, extract_author_orcids_from_html


DATABASE_URL = "postgresql+psycopg://mephi:mephi@localhost:5432/mephi_journals"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MEPhI-Journals-Dashboard/0.1)"}


def fetch_orcids(article: tuple[int, str]) -> tuple[int, dict[str, str], str | None]:
    article_id, url = article
    try:
        response = requests.get(url, headers=HEADERS, timeout=12)
        response.raise_for_status()
    except requests.RequestException as exc:
        return article_id, {}, str(exc)
    return article_id, extract_author_orcids_from_html(response.text), None


def merge_affiliations(left: str | None, right: str | None) -> str | None:
    parts: list[str] = []
    for value in [left, right]:
        for part in (value or "").split(";"):
            part = part.strip()
            if part and part not in parts:
                parts.append(part)
    return "; ".join(parts) if parts else None


def get_or_create_author(conn, name: str, orcid: str) -> int:
    existing = conn.execute(
        text("select author_id from author where name = :name and orcid = :orcid limit 1"),
        {"name": name, "orcid": orcid},
    ).scalar()
    if existing:
        return int(existing)
    return int(conn.execute(
        text("insert into author (name, orcid) values (:name, :orcid) returning author_id"),
        {"name": name, "orcid": orcid},
    ).scalar_one())


def apply_article_orcids(engine, article_id: int, orcids_by_name: dict[str, str]) -> int:
    moved = 0
    orcids_by_key = {
        key: orcid
        for name, orcid in orcids_by_name.items()
        if (key := author_match_key(name))
    }
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                select aa.article_id, aa.author_id, au.name, au.orcid,
                       aa.affiliation_raw, aa.is_mephi, aa.author_order
                from article_author aa
                join author au on au.author_id = aa.author_id
                where aa.article_id = :article_id
                order by aa.author_order, au.author_id
            """),
            {"article_id": article_id},
        ).mappings().all()

        ordered_orcids = list(orcids_by_name.values())
        can_match_by_order = len(ordered_orcids) == len(rows)

        for index, row in enumerate(rows):
            orcid = orcids_by_key.get(author_match_key(row["name"]) or "")
            if not orcid and can_match_by_order:
                orcid = ordered_orcids[index]
            if not orcid or row["orcid"] == orcid:
                continue

            target_author_id = get_or_create_author(conn, row["name"], orcid)
            if target_author_id == row["author_id"]:
                continue

            target_link = conn.execute(
                text("""
                    select affiliation_raw, is_mephi, author_order
                    from article_author
                    where article_id = :article_id and author_id = :author_id
                """),
                {"article_id": article_id, "author_id": target_author_id},
            ).mappings().first()

            if target_link:
                conn.execute(
                    text("""
                        update article_author
                        set affiliation_raw = :affiliation_raw,
                            is_mephi = :is_mephi,
                            author_order = :author_order
                        where article_id = :article_id and author_id = :author_id
                    """),
                    {
                        "article_id": article_id,
                        "author_id": target_author_id,
                        "affiliation_raw": merge_affiliations(target_link["affiliation_raw"], row["affiliation_raw"]),
                        "is_mephi": bool(target_link["is_mephi"]) or bool(row["is_mephi"]),
                        "author_order": min(target_link["author_order"] or 0, row["author_order"] or 0),
                    },
                )
                conn.execute(
                    text("delete from article_author where article_id = :article_id and author_id = :author_id"),
                    {"article_id": article_id, "author_id": row["author_id"]},
                )
            else:
                conn.execute(
                    text("""
                        update article_author
                        set author_id = :target_author_id
                        where article_id = :article_id and author_id = :source_author_id
                    """),
                    {
                        "article_id": article_id,
                        "source_author_id": row["author_id"],
                        "target_author_id": target_author_id,
                    },
                )
            moved += 1
    return moved


def main() -> None:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        articles = conn.execute(
            text("""
                select distinct a.article_id, a.url
                from article a
                join article_author aa on aa.article_id = a.article_id
                join author au on au.author_id = aa.author_id
                where a.url is not null and au.orcid is null
                order by a.article_id
            """)
        ).all()

    checked = found_articles = moved_links = errors = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_orcids, article) for article in articles]
        for future in as_completed(futures):
            article_id, orcids_by_name, error = future.result()
            checked += 1
            if error:
                errors += 1
                continue
            if not orcids_by_name:
                continue
            found_articles += 1
            moved_links += apply_article_orcids(engine, article_id, orcids_by_name)
            if checked % 100 == 0:
                print(f"checked={checked} found_articles={found_articles} moved_links={moved_links} errors={errors}", flush=True)

    print(f"checked={checked} found_articles={found_articles} moved_links={moved_links} errors={errors}")


if __name__ == "__main__":
    main()
