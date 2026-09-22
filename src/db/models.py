from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Journal(Base):
    __tablename__ = "journal"

    journal_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    url: Mapped[str] = mapped_column(Text)
    source_key: Mapped[str] = mapped_column(String(50), unique=True)
    collector: Mapped[str | None] = mapped_column(String(50), nullable=True)


class Article(Base):
    __tablename__ = "article"

    article_id: Mapped[int] = mapped_column(primary_key=True)
    journal_id: Mapped[int] = mapped_column(ForeignKey("journal.journal_id", ondelete="CASCADE"))
    source_article_id: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(Text)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publication_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume: Mapped[str | None] = mapped_column(String(50), nullable=True)
    issue: Mapped[str | None] = mapped_column(String(50), nullable=True)
    funding_section_found: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    parsed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("journal_id", "source_article_id"),)


class Author(Base):
    __tablename__ = "author"

    author_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    orcid: Mapped[str | None] = mapped_column(String(50), nullable=True)

    __table_args__ = (UniqueConstraint("name", "orcid"),)


class ArticleAuthor(Base):
    __tablename__ = "article_author"

    article_id: Mapped[int] = mapped_column(ForeignKey("article.article_id", ondelete="CASCADE"), primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("author.author_id", ondelete="CASCADE"), primary_key=True)
    affiliation_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_mephi: Mapped[bool] = mapped_column(Boolean, default=False)
    author_order: Mapped[int] = mapped_column(Integer, default=0)


class Grant(Base):
    __tablename__ = "grant"

    grant_id: Mapped[int] = mapped_column(primary_key=True)
    funder_normalized: Mapped[str] = mapped_column(String(255))
    grant_number: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("funder_normalized", "grant_number"),)


class ArticleGrant(Base):
    __tablename__ = "article_grant"

    article_id: Mapped[int] = mapped_column(ForeignKey("article.article_id", ondelete="CASCADE"), primary_key=True)
    grant_id: Mapped[int] = mapped_column(ForeignKey("grant.grant_id", ondelete="CASCADE"), primary_key=True)
    funding_text_raw: Mapped[str] = mapped_column(Text)
    funder_raw: Mapped[str] = mapped_column(Text)


class JournalUpdateLog(Base):
    __tablename__ = "journal_update_log"

    log_id: Mapped[int] = mapped_column(primary_key=True)
    journal_id: Mapped[int | None] = mapped_column(ForeignKey("journal.journal_id", ondelete="SET NULL"), nullable=True)
    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pages_checked: Mapped[int] = mapped_column(Integer, default=0)
    articles_checked: Mapped[int] = mapped_column(Integer, default=0)
    articles_changed: Mapped[int] = mapped_column(Integer, default=0)
