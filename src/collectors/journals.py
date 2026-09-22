from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JournalSource:
    source_key: str
    name: str
    url: str
    collector: str | None = None


MEPHI_JOURNALS = [
    JournalSource(
        source_key="nucet",
        name="Nuclear Energy and Technology",
        url="https://nucet.pensoft.net",
        collector="pensoft_nucet",
    ),
    JournalSource(
        source_key="bit",
        name="Безопасность информационных технологий",
        url="https://bit.spels.ru",
        collector="oai_bit",
    ),
    JournalSource(
        source_key="vestnik_mephi",
        name="Вестник НИЯУ МИФИ",
        url="https://vestnikmephi.elpub.ru",
        collector="oai_vestnik_mephi",
    ),
    JournalSource(
        source_key="global_nuclear_safety",
        name="Глобальная ядерная безопасность",
        url="https://glonucsec.elpub.ru",
        collector="oai_global_nuclear_safety",
    ),
    JournalSource(
        source_key="nuclear_power_engineering",
        name="Известия вузов. Ядерная энергетика",
        url="https://nuclear-power-engineering.ru",
        collector="rss_nuclear_power_engineering",
    ),
    JournalSource(
        source_key="scientific_visualization",
        name="Научная визуализация",
        url="https://sv-journal.org",
        collector="html_scientific_visualization",
    ),
    JournalSource(
        source_key="nuclear_physics_engineering",
        name="Ядерная физика и инжиниринг",
        url="https://npe.elpub.ru",
        collector="oai_nuclear_physics_engineering",
    ),
]
