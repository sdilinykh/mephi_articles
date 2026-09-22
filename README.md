# MEPhI Journals Dashboard

Локальный Streamlit-дашборд для сбора и просмотра статей журналов МИФИ,
авторов, аффиляций, DOI, грантовой поддержки и логов обновления.

## Что собирается

- 7 журналов из списка МИФИ.
- Статьи, DOI, даты, тома/выпуски и ссылки.
- Авторы, ORCID и аффиляции.
- Признак автора/аффиляции МИФИ.
- Релевантные разделы funding/acknowledgements/благодарности: раздел
  учитывается только если внутри написано про поддержку, финансирование,
  оборудование, установки, измерения, вычислительные ресурсы и т.п.
- Грантодатель и номер гранта, если он найден.
- Логи каждой загрузки.

Если у статьи есть JATS/XML, collector использует XML преимущественно. Если XML
недоступен, используется fallback на HTML/OAI/RSS. PDF сейчас не парсится.

## Требования

- Docker Desktop или OrbStack

## Первый запуск

```bash
cp .env.example .env
docker compose up -d
```

Дашборд откроется по адресу:

```text
http://localhost:8501
```

При первом запуске образ соберётся автоматически. База данных создаётся при
первом запуске `updater`.

Загрузить данные:

```bash
docker compose run --rm updater --all
```

## Обновление данных

Инкрементальное обновление всех журналов:

```bash
docker compose run --rm updater --all
```

Обновить один журнал:

```bash
docker compose run --rm updater --source vestnik_mephi
```

Ограничить количество записей для быстрой проверки:

```bash
docker compose run --rm updater --source vestnik_mephi --max-records 1
```

Полностью пересоздать базу и загрузить заново:

```bash
docker compose run --rm updater --reset --all
```

## Еженедельное обновление на macOS

Скрипт:

```bash
scripts/weekly_update.sh
```

Расписание `launchd`: понедельник, 02:00. Это соответствует ночи с
воскресенья на понедельник.

Установка:

```bash
mkdir -p ~/Library/LaunchAgents
cp launchd/mephi-journals-weekly-update.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/mephi-journals-weekly-update.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/mephi-journals-weekly-update.plist
```

Логи:

```text
logs/weekly_update.out.log
logs/weekly_update.err.log
```

Если проект лежит в `Desktop`, `Documents` или другой защищенной macOS папке,
`launchd` может получить `Operation not permitted`. В этом случае перенесите
проект, например в `~/Projects/mephi-journals-dashboard`, или дайте Terminal /
используемому shell Full Disk Access в System Settings.

## Основные вкладки

- `Обзор` — агрегаты и графики, включая группы статей по грантовой поддержке.
- `Витрина` — объединение журнал-статья-грант.
- `journal`, `article`, `author`, `article_author`, `grant`, `article_grant` —
  исходные нормализованные таблицы.
- `логи` — журнал загрузок.

## Группы грантов

В обзоре статьи делятся на три группы:

- `а) нет релевантного раздела благодарности/финансирования`
- `б) есть раздел и номер гранта`
- `в) есть раздел, но номер гранта не найден`

Гранты считаются только из релевантного раздела. Упоминания фондов и номеров
в основном тексте статьи вне такого раздела игнорируются.

Для точной классификации старых статей после изменения парсеров выполните
полную перезагрузку:

```bash
docker compose run --rm updater --reset --all
```
