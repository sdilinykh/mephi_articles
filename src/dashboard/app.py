import pandas as pd
import streamlit as st
import altair as alt
from sqlalchemy import text

from src.db.database import engine


st.set_page_config(page_title="Научные журналы МИФИ", layout="wide")
st.title("Научные журналы МИФИ")


@st.cache_data(ttl=60)
def load_table(query: str) -> pd.DataFrame:
    return pd.read_sql(text(query), engine)


journals_df = load_table("""
SELECT
    journal_id,
    name,
    url,
    source_key,
    collector,
    CASE WHEN collector IS NULL THEN 'unsupported' ELSE 'supported' END AS collector_status
FROM journal
ORDER BY journal_id
""")
articles_df = load_table("""
SELECT
    a.article_id,
    a.journal_id,
    j.name AS journal_name,
    a.source_article_id,
    a.title,
    a.doi,
    a.publication_date,
    a.year,
    a.volume,
    a.issue,
    a.funding_section_found,
    a.url,
    a.first_seen_at,
    a.last_seen_at,
    a.parsed_at
FROM article a
JOIN journal j ON j.journal_id = a.journal_id
ORDER BY a.article_id DESC
""")
authors_df = load_table("""
WITH author_affiliations AS (
    SELECT
        au.author_id,
        au.name,
        au.orcid,
        nullif(trim(aff.affiliation), '') AS affiliation_raw
    FROM author au
    LEFT JOIN article_author aa ON aa.author_id = au.author_id
    LEFT JOIN LATERAL regexp_split_to_table(aa.affiliation_raw, '\\s*;\\s*') AS aff(affiliation)
        ON aa.affiliation_raw IS NOT NULL AND aa.affiliation_raw <> ''
),
author_affiliation_rows AS (
    SELECT
        author_id,
        name,
        orcid,
        affiliation_raw,
        count(affiliation_raw) OVER (PARTITION BY author_id) AS real_affiliations
    FROM author_affiliations
)
SELECT
    author_id,
    name,
    orcid,
    affiliation_raw,
    CASE
        WHEN affiliation_raw ILIKE '%MEPhI%'
          OR affiliation_raw ILIKE '%MIFI%'
          OR affiliation_raw ILIKE '%Moscow Engineering Physics Institute%'
          OR affiliation_raw ILIKE '%МИФИ%'
          OR affiliation_raw ILIKE '%Национальн%исследовательск%ядерн%университет%МИФИ%'
        THEN true
        ELSE false
    END AS is_mephi
FROM author_affiliation_rows
WHERE affiliation_raw IS NOT NULL OR real_affiliations = 0
GROUP BY author_id, name, orcid, affiliation_raw
ORDER BY author_id, affiliation_raw NULLS LAST
""")
article_authors_df = load_table("""
SELECT
    aa.article_id,
    aa.author_id,
    a.title,
    au.name AS author_name,
    au.orcid,
    CASE
        WHEN nullif(trim(aff.affiliation), '') ~* '(IATE|Obninsk Institute for Nuclear Power Engineering).*?(MEPhI|МИФИ)' THEN 'IATE MEPhI'
        WHEN nullif(trim(aff.affiliation), '') ~* '(INPhE MEPhI|MEPhI|NRNU MEPhI|National Research Nuclear University MEPhI|НИЯУ МИФИ|Национальн.*исследовательск.*ядерн.*университет.*МИФИ)' THEN 'National Research Nuclear University MEPhI'
        WHEN nullif(trim(aff.affiliation), '') ~* '(IPPE|Leypunsky|Leipunsky|Лейпунск)' THEN 'JSC "SSC RF-IPPE n.a. A.I. Leypunsky"'
        WHEN nullif(trim(aff.affiliation), '') ~* '(Kurchatov Institute|Курчатовск)' THEN 'National Research Center "Kurchatov Institute"'
        WHEN nullif(trim(aff.affiliation), '') ~* '(NIKIET|Dollezhal)' THEN 'NIKIET JSC'
        WHEN nullif(trim(aff.affiliation), '') ~* '(IBRAE|Nuclear Safety Institute)' THEN 'Nuclear Safety Institute of the Russian Academy of Sciences'
        WHEN nullif(trim(aff.affiliation), '') ~* 'Nizhny Novgorod State Technical University' THEN 'Nizhny Novgorod State Technical University n.a. R.E. Alekseev'
        ELSE nullif(trim(aff.affiliation), '')
    END AS affiliation_raw,
    CASE
        WHEN nullif(trim(aff.affiliation), '') ILIKE '%MEPhI%'
          OR nullif(trim(aff.affiliation), '') ILIKE '%MIFI%'
          OR nullif(trim(aff.affiliation), '') ILIKE '%Moscow Engineering Physics Institute%'
          OR nullif(trim(aff.affiliation), '') ILIKE '%МИФИ%'
          OR nullif(trim(aff.affiliation), '') ILIKE '%Национальн%исследовательск%ядерн%университет%МИФИ%'
        THEN true
        ELSE false
    END AS is_mephi,
    aa.author_order
FROM article_author aa
JOIN article a ON a.article_id = aa.article_id
JOIN author au ON au.author_id = aa.author_id
LEFT JOIN LATERAL regexp_split_to_table(aa.affiliation_raw, '\\s*;\\s*') AS aff(affiliation)
    ON aa.affiliation_raw IS NOT NULL AND aa.affiliation_raw <> ''
ORDER BY aa.article_id DESC, aa.author_order, affiliation_raw NULLS LAST
""")
grants_df = load_table("""
SELECT grant_id, funder_normalized, grant_number
FROM "grant"
ORDER BY grant_id
""")
article_grants_df = load_table("""
SELECT
    ag.article_id,
    ag.grant_id,
    j.name AS journal_name,
    a.title,
    a.doi,
    a.url,
    COALESCE(a.funding_section_found, FALSE) AS funding_section_found,
    g.funder_normalized,
    g.grant_number,
    ag.funder_raw,
    ag.funding_text_raw
FROM article_grant ag
JOIN article a ON a.article_id = ag.article_id
JOIN journal j ON j.journal_id = a.journal_id
JOIN "grant" g ON g.grant_id = ag.grant_id
ORDER BY ag.article_id DESC, ag.grant_id
""")
article_funding_status_df = load_table("""
SELECT
    a.article_id,
    j.name AS journal_name,
    CASE
        WHEN COALESCE(a.funding_section_found, FALSE) = FALSE
            THEN 'а) нет релевантного раздела благодарности/финансирования'
        WHEN EXISTS (
            SELECT 1
            FROM article_grant ag
            JOIN "grant" g ON g.grant_id = ag.grant_id
            WHERE ag.article_id = a.article_id
              AND NULLIF(trim(g.grant_number), '') IS NOT NULL
        )
            THEN 'б) есть раздел и номер гранта'
        ELSE 'в) есть раздел, но номер гранта не найден'
    END AS grant_group
FROM article a
JOIN journal j ON j.journal_id = a.journal_id
""")
logs_df = load_table("""
SELECT
    l.log_id,
    l.journal_id,
    j.name AS journal_name,
    l.started_at,
    l.finished_at,
    l.status,
    l.message,
    l.pages_checked,
    l.articles_checked,
    l.articles_changed
FROM journal_update_log l
LEFT JOIN journal j ON j.journal_id = l.journal_id
ORDER BY l.log_id DESC
""")

if journals_df.empty:
    st.info("База пока пуста. Сначала запустите pipeline обновления.")
    st.stop()

counted_article_grants_df = article_grants_df[article_grants_df["funding_section_found"]]
mephi_article_ids = set(article_authors_df.loc[article_authors_df["is_mephi"], "article_id"])
funded_article_ids = set(counted_article_grants_df["article_id"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Журналов", len(journals_df))
c2.metric("Статей", len(articles_df))
c3.metric("С финансированием", len(funded_article_ids))
c4.metric("С авторами МИФИ", len(mephi_article_ids))

link_config = {
    "url": st.column_config.LinkColumn("Ссылка", display_text="Открыть"),
    "doi": st.column_config.TextColumn("DOI"),
}


def text_filter(data: pd.DataFrame, columns: list[str], value: str) -> pd.DataFrame:
    if not value:
        return data
    haystack = pd.Series("", index=data.index)
    for column in columns:
        haystack = haystack + " " + data[column].fillna("").astype(str)
    return data[haystack.str.lower().str.contains(value.lower(), regex=False)]


def option_filter(data: pd.DataFrame, column: str, label: str, key: str) -> pd.DataFrame:
    values = sorted(x for x in data[column].dropna().unique())
    selected = st.multiselect(label, values, key=key)
    return data[data[column].isin(selected)] if selected else data


def boolean_filter(data: pd.DataFrame, column: str, label: str, key: str) -> pd.DataFrame:
    selected = st.selectbox(label, ["Все", "Да", "Нет"], key=key)
    if selected == "Да":
        return data[data[column]]
    if selected == "Нет":
        return data[~data[column]]
    return data


def year_filter(data: pd.DataFrame, column: str, label: str, key: str) -> pd.DataFrame:
    years = sorted(data[column].dropna().astype(int).unique(), reverse=True)
    selected = st.multiselect(label, years, key=key)
    return data[data[column].isin(selected)] if selected else data


def date_filter(data: pd.DataFrame, column: str, label: str, key: str) -> pd.DataFrame:
    if data[column].dropna().empty:
        st.date_input(label, value=None, key=key, disabled=True)
        return data

    dates = pd.to_datetime(data[column], errors="coerce").dropna()
    if dates.empty:
        st.date_input(label, value=None, key=key, disabled=True)
        return data

    min_date = dates.min().date()
    max_date = dates.max().date()
    selected = st.date_input(label, value=(min_date, max_date), key=key)
    if not isinstance(selected, tuple) or len(selected) != 2:
        return data
    start, end = selected
    if start is None or end is None:
        return data

    current = pd.to_datetime(data[column], errors="coerce").dt.date
    return data[current.between(start, end)]


overview_tab, combined_tab, journals_tab, articles_tab, authors_tab, article_authors_tab, grants_tab, article_grants_tab, logs_tab = st.tabs(
    ["Обзор", "Витрина", "journal", "article", "author", "article_author", "grant", "article_grant", "логи"]
)

with overview_tab:
    st.subheader("Группы статей по грантовой поддержке")
    if article_funding_status_df.empty:
        st.info("Нет данных для группировки грантов.")
    else:
        grant_group_chart = (
            article_funding_status_df
            .pivot_table(index="journal_name", columns="grant_group", values="article_id", aggfunc="nunique", fill_value=0)
            .sort_index()
        )
        grant_group_long = grant_group_chart.reset_index().melt(
            id_vars="journal_name",
            var_name="grant_group",
            value_name="articles",
        )
        totals = grant_group_chart.sum(axis=1).rename("total_articles").reset_index()
        grant_group_long = grant_group_long.merge(totals, on="journal_name", how="left")
        grant_group_long["share_percent"] = (
            grant_group_long["articles"] / grant_group_long["total_articles"] * 100
        ).fillna(0)
        visible_groups = grant_group_long[
            grant_group_long["grant_group"] != "а) нет релевантного раздела благодарности/финансирования"
        ].copy()

        if visible_groups["articles"].sum() == 0:
            st.info("Релевантные разделы поддержки пока не найдены.")
        else:
            chart = (
                alt.Chart(visible_groups)
                .mark_bar()
                .encode(
                    x=alt.X("journal_name:N", title="Журнал", sort="-y"),
                    y=alt.Y("share_percent:Q", title="Доля от всех статей журнала, %"),
                    color=alt.Color("grant_group:N", title="Группа"),
                    tooltip=[
                        alt.Tooltip("journal_name:N", title="Журнал"),
                        alt.Tooltip("grant_group:N", title="Группа"),
                        alt.Tooltip("articles:Q", title="Статей"),
                        alt.Tooltip("share_percent:Q", title="Доля, %", format=".2f"),
                    ],
                )
                .properties(height=360)
            )
            st.altair_chart(chart, use_container_width=True)

        with st.expander("Все группы: абсолютные значения и доли"):
            st.dataframe(
                grant_group_long.sort_values(["journal_name", "grant_group"]),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "share_percent": st.column_config.NumberColumn("share_percent", format="%.2f%%"),
                },
            )

    st.subheader("Статьи с финансированием по грантодателям")
    if counted_article_grants_df.empty:
        st.info("Гранты пока не найдены.")
    else:
        chart = (
            counted_article_grants_df.groupby("funder_normalized")["article_id"]
            .nunique()
            .sort_values(ascending=False)
        )
        st.bar_chart(chart)

    st.subheader("Статьи авторов МИФИ с финансированием")
    mephi_funded = counted_article_grants_df[counted_article_grants_df["article_id"].isin(mephi_article_ids)]
    if mephi_funded.empty:
        st.info("Нет статей с авторами МИФИ и найденным финансированием.")
    else:
        st.bar_chart(
            mephi_funded.groupby("funder_normalized")["article_id"]
            .nunique()
            .sort_values(ascending=False)
        )

with combined_tab:
    st.subheader("Витрина статей и финансирования")
    data = articles_df.merge(
        counted_article_grants_df[["article_id", "grant_id", "funder_normalized", "grant_number", "funder_raw", "funding_text_raw"]],
        on="article_id",
        how="left",
    )
    data["grant_group"] = data["article_id"].map(
        article_funding_status_df.set_index("article_id")["grant_group"]
    )
    data["has_mephi_author"] = data["article_id"].isin(mephi_article_ids)

    c1, c2, c3, c4, c5 = st.columns([1.3, 1.2, 1.2, 1.2, 2])
    with c1:
        selected_journals = st.multiselect("Журнал", sorted(data["journal_name"].dropna().unique()), key="showcase_journal")
    with c2:
        funding_filter = st.selectbox("Финансирование", ["Все", "Есть", "Нет"], key="showcase_funding")
    with c3:
        mephi_filter = st.selectbox("МИФИ автор", ["Все", "Да", "Нет"], key="showcase_mephi")
    with c4:
        years = sorted(data["year"].dropna().astype(int).unique(), reverse=True)
        selected_years = st.multiselect("Год", years, key="showcase_year")
    with c5:
        search = st.text_input("Поиск", key="showcase_search")

    if selected_journals:
        data = data[data["journal_name"].isin(selected_journals)]
    if funding_filter == "Есть":
        data = data[data["funder_normalized"].notna()]
    elif funding_filter == "Нет":
        data = data[data["funder_normalized"].isna()]
    if mephi_filter == "Да":
        data = data[data["has_mephi_author"]]
    elif mephi_filter == "Нет":
        data = data[~data["has_mephi_author"]]
    if selected_years:
        data = data[data["year"].isin(selected_years)]
    data = text_filter(data, ["journal_name", "title", "doi", "funder_normalized", "grant_number", "grant_group"], search)

    filtered_articles = data["article_id"].nunique() if not data.empty else 0
    filtered_funded = data.loc[data["funder_normalized"].notna(), "article_id"].nunique() if not data.empty else 0
    filtered_mephi = data.loc[data["has_mephi_author"], "article_id"].nunique() if not data.empty else 0
    m1, m2, m3 = st.columns(3)
    m1.metric(
        "Статей в выборке",
        filtered_articles,
    )
    m2.metric(
        "С финансированием",
        filtered_funded,
    )
    m3.metric(
        "С авторами МИФИ",
        filtered_mephi,
    )

    st.caption(f"Строк: {len(data)}; статей: {filtered_articles}")
    showcase_columns = [
        "journal_name",
        "article_id",
        "title",
        "doi",
        "url",
        "grant_group",
        "grant_id",
        "funder_normalized",
        "grant_number",
        "funder_raw",
        "funding_text_raw",
        "year",
        "volume",
        "issue",
        "has_mephi_author",
    ]
    st.dataframe(data[[c for c in showcase_columns if c in data.columns]], use_container_width=True, hide_index=True, column_config=link_config)

with journals_tab:
    st.subheader("Таблица journal")
    c1, c2, c3 = st.columns([2, 1.3, 1.3])
    with c1:
        query = st.text_input("Поиск по journal", key="journal_search")
    with c2:
        data = option_filter(journals_df.copy(), "collector_status", "Статус collector", "journal_collector_status")
    with c3:
        data = option_filter(data, "source_key", "Source key", "journal_source_key")
    data = text_filter(data, ["name", "url", "source_key", "collector", "collector_status"], query)
    st.caption(f"Строк: {len(data)}")
    st.dataframe(data, use_container_width=True, hide_index=True, column_config=link_config)

with articles_tab:
    c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.2, 1.2, 1.6])
    data = articles_df.copy()
    with c1:
        query = st.text_input("Поиск по article", key="article_search")
    with c2:
        data = option_filter(data, "journal_name", "Журнал", "article_journal")
    with c3:
        data = year_filter(data, "year", "Год", "article_year")
    with c4:
        data = option_filter(data, "volume", "Том", "article_volume")
    with c5:
        data = date_filter(data, "publication_date", "Дата публикации", "article_pub_date")
    data = text_filter(data, ["journal_name", "title", "doi", "source_article_id", "year", "volume", "issue"], query)
    st.caption(f"Строк: {len(data)}")
    st.dataframe(data, use_container_width=True, hide_index=True, column_config=link_config)

with authors_tab:
    c1, c2, c3 = st.columns([2, 1, 1])
    data = authors_df.copy()
    with c1:
        query = st.text_input("Поиск по author", key="author_search")
    with c2:
        orcid_filter = st.selectbox("ORCID", ["Все", "Есть", "Нет"], key="author_orcid")
    with c3:
        data = boolean_filter(data, "is_mephi", "МИФИ", "author_mephi")
    if orcid_filter == "Есть":
        data = data[data["orcid"].notna()]
    elif orcid_filter == "Нет":
        data = data[data["orcid"].isna()]
    data = text_filter(data, ["name", "orcid", "affiliation_raw"], query)
    st.caption(f"Строк: {len(data)}")
    st.dataframe(data, use_container_width=True, hide_index=True)

with article_authors_tab:
    c1, c2, c3 = st.columns([1, 1.5, 2])
    data = article_authors_df.copy()
    with c1:
        data = boolean_filter(data, "is_mephi", "МИФИ", "aa_mephi")
    with c2:
        data = option_filter(data, "author_name", "Автор", "aa_author")
    with c3:
        query = st.text_input("Поиск по article_author", key="aa_search")
    data = text_filter(data, ["title", "author_name", "orcid", "affiliation_raw"], query)
    st.caption(f"Строк: {len(data)}")
    st.dataframe(data, use_container_width=True, hide_index=True)

with grants_tab:
    c1, c2, c3 = st.columns([2, 1.5, 1.5])
    data = grants_df.copy()
    with c1:
        query = st.text_input("Поиск по grant", key="grant_search")
    with c2:
        data = option_filter(data, "funder_normalized", "Грантодатель", "grant_funder")
    with c3:
        grant_number_filter = st.selectbox("Номер гранта", ["Все", "Есть", "Нет"], key="grant_number_filter")
    if grant_number_filter == "Есть":
        data = data[data["grant_number"].notna()]
    elif grant_number_filter == "Нет":
        data = data[data["grant_number"].isna()]
    data = text_filter(data, ["funder_normalized", "grant_number"], query)
    st.caption(f"Строк: {len(data)}")
    st.dataframe(data, use_container_width=True, hide_index=True)

with article_grants_tab:
    c1, c2, c3 = st.columns([1.5, 1.3, 2])
    data = article_grants_df.copy()
    with c1:
        data = option_filter(data, "funder_normalized", "Грантодатель", "ag_funders")
    with c2:
        grant_number_filter = st.selectbox("Номер гранта", ["Все", "Есть", "Нет"], key="ag_grant_number")
    with c3:
        query = st.text_input("Поиск по article_grant", key="ag_search")
    if grant_number_filter == "Есть":
        data = data[data["grant_number"].notna()]
    elif grant_number_filter == "Нет":
        data = data[data["grant_number"].isna()]
    data = text_filter(data, ["title", "doi", "funder_normalized", "grant_number", "funder_raw", "funding_text_raw"], query)
    st.caption(f"Строк: {len(data)}")
    st.dataframe(data, use_container_width=True, hide_index=True, column_config=link_config)

with logs_tab:
    data = logs_df.copy()
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.7, 2])
    with c1:
        data = option_filter(data, "status", "Статус", "logs_status")
    with c2:
        data = option_filter(data, "journal_name", "Журнал", "logs_journal")
    with c3:
        data = date_filter(data, "started_at", "Дата запуска", "logs_started")
    with c4:
        query = st.text_input("Поиск по логам", key="logs_search")
    data = text_filter(data, ["journal_name", "status", "message"], query)
    st.caption(f"Строк: {len(data)}")
    st.dataframe(data, use_container_width=True, hide_index=True)
