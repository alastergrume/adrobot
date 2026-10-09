# Adrobot · Keitaro wrapper

Тестовое задание: надстройка над рекламным трекером Keitaro на FastAPI + SQLAlchemy.

1. **Создатель кампаний.** Название, гео и оффер → в Keitaro создаётся кампания с двумя потоками:
   Flow 1 ловит посетителей из указанных стран и редиректит на `https://google.com`,
   Flow 2 отправляет всех остальных на выбранный оффер.
2. **Редактор кампании.** Загружает потоки из Keitaro и позволяет добавлять, удалять и возвращать офферы,
   закреплять доли и публиковать изменения в Keitaro. Логика повторяет редактор из видео к заданию.

Приложение работает с Keitaro только через его Admin API. Для проверки без доступа к трекеру есть
тестовое окружение (`docker/docker-compose-test.yml`): поддельный сервис Keitaro, который отвечает
по тому же API, тестовая база и приложение с `APP_ENV=TEST`. Так сценарии прогоняются на живых страницах,
а код работы с API остаётся боевым.

## Запуск

База данных — PostgreSQL 16, она поднимается как сервис docker-compose.
Нужен Docker с Compose v2 (на Windows — Docker Desktop). Все файлы Docker лежат в папке `docker/`.

| Окружение | Compose-файл | `APP_ENV` | Файл настроек | Keitaro |
|---|---|---|---|---|
| Production | `docker/docker-compose.yml` | `PRODUCTION` | `app/configs/.env` | настоящий трекер |
| Тестовое | `docker/docker-compose-test.yml` | `TEST` | `app/configs/.env_test` | поддельный сервис `tests/keitaro_service` |

### Тестовое окружение (без доступа к Keitaro)

Из корня проекта:

```bash
docker compose -f docker/docker-compose-test.yml up --build
```

| Сервис | Что это | Адрес |
|---|---|---|
| `db-test` | тестовая база PostgreSQL, создаётся заново при каждом старте | localhost:5433 |
| `keitaro` | поддельный Keitaro: Admin API и страница «админки» | http://localhost:8081/admin/ |
| `app` | приложение с `APP_ENV=TEST` | http://localhost:8000 |

Поддельный Keitaro при первом старте заполняется тестовыми данными из
`tests/keitaro_service/seed_test_data.py` (кампания «campaign 2» из видео и несколько офферов).
На его странице можно удалить оффер «прямо в Keitaro» и проверить синхронизацию в приложении,
а кнопка **Reset to test data** возвращает исходные данные. То же из командной строки:

```bash
docker compose -f docker/docker-compose-test.yml exec keitaro python -m tests.keitaro_service.seed_test_data
```

### Production

1. Скопировать `app/configs/.env.example` в `app/configs/.env` и указать адрес Keitaro и API-ключ
   (см. «Подключение к Keitaro»).
2. Запустить:

```bash
docker compose -f docker/docker-compose.yml up --build
```

Поднимаются `db` (PostgreSQL) и `app` (приложение на http://localhost:8000).
Приложение ждёт готовности базы и применяет миграции при старте. Данные базы хранятся в томе `pgdata`.

```bash
docker compose -f docker/docker-compose.yml exec app alembic upgrade head   # миграции вручную
docker compose -f docker/docker-compose.yml down -v                         # остановить и удалить данные
```

### Приложение локально, сервисы в Docker

Удобно для разработки. Нужен Python 3.10 или новее.

```bash
git clone https://github.com/<your-username>/adrobot.git
cd adrobot

python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

С поддельным Keitaro и тестовой базой (настройки из `app/configs/.env_test`):

```bash
docker compose -f docker/docker-compose-test.yml up -d db-test keitaro

set APP_ENV=TEST                  # PowerShell: $env:APP_ENV="TEST"; Linux/macOS: export APP_ENV=TEST
alembic upgrade head
uvicorn app.main:app --reload
```

С настоящим Keitaro (настройки из `app/configs/.env`):

```bash
docker compose -f docker/docker-compose.yml up -d db   # PostgreSQL на localhost:5432

copy app\configs\.env.example app\configs\.env   # Linux/macOS: cp app/configs/.env.example app/configs/.env
alembic upgrade head
uvicorn app.main:app --reload
```

Открыть http://127.0.0.1:8000. Документация API — http://127.0.0.1:8000/docs.

Поддельный Keitaro можно запустить и без Docker: `uvicorn tests.keitaro_service.app:app --port 8081`
(данные лежат в `tests/keitaro_service/.data/`).

Если порты заняты, их можно поменять переменными `POSTGRES_PORT` (production-база),
`POSTGRES_TEST_PORT`, `KEITARO_TEST_PORT` и `APP_TEST_PORT` при запуске docker compose; тогда поправьте
адреса в файле настроек.

## Миграции

Схема базы управляется Alembic, адрес базы берётся из `DATABASE_URL` текущего окружения
(`app/configs/.env` или `app/configs/.env_test`, в зависимости от `APP_ENV`).

```bash
alembic upgrade head                                  # применить все миграции
alembic downgrade -1                                  # откатить последнюю
alembic revision --autogenerate -m "describe change"  # создать миграцию после изменения app/models.py
```

В Docker миграции применяются автоматически при старте сервиса `app` в обоих окружениях.

## Настройки

Настройки описаны классами pydantic-settings в папке `app/configs/`. Базовый класс `EnvSettings` (`env.py`)
выбирает файл настроек по переменной `APP_ENV`, а от него наследуются классы по областям применения,
каждый со своим префиксом переменных. Переменные окружения важнее значений из файла.

| `APP_ENV` | Файл |
|---|---|
| `PRODUCTION` (по умолчанию) | `app/configs/.env` — создаётся из `app/configs/.env.example`, в git не попадает |
| `TEST` | `app/configs/.env_test` — тестовое окружение, хранится в git |

Готовые объекты создаются в `app/configs/__init__.py`, модули импортируют их оттуда:
`from app.configs import keitaro_settings`.

| Объект | Класс, файл | Переменные |
|---|---|---|
| `database_settings` | `DatabaseSettings`, `database.py` | `DATABASE_URL` |
| `keitaro_settings` | `KeitaroSettings`, `keitaro.py` | `KEITARO_URL`, `KEITARO_API_KEY`, `KEITARO_TIMEOUT_S`, `KEITARO_ADMIN_URL` |
| `campaign_settings` | `CampaignSettings`, `campaign.py` | `CAMPAIGN_DOMAIN`, `CAMPAIGN_GROUP`, `CAMPAIGN_SOURCE`, `CAMPAIGN_GEO_REDIRECT_URL` |

Ключ API хранится как `SecretStr` и не попадает в логи и сообщения об ошибках. Если Keitaro не настроен,
приложение запускается, но на страницах и в API сообщает, какие переменные нужно указать.

## Подключение к Keitaro

В `app/configs/.env`:

```
KEITARO_URL=https://адрес-трекера
KEITARO_API_KEY=ключ из Профиль → API ключи
```

Клиент обращается к `KEITARO_URL/admin_api/v1` с заголовком `Api-Key`. Ссылки «View in KT» ведут
в админку Keitaro (`KEITARO_ADMIN_URL`, если задан, иначе `KEITARO_URL`).
Домен, группа и источник новых кампаний ищутся в Keitaro по именам из `CAMPAIGN_DOMAIN`,
`CAMPAIGN_GROUP` и `CAMPAIGN_SOURCE` (по умолчанию `in.posdk.xyz` и `FORTESTS`, как на скриншотах из задания).

## Как пользоваться

1. На странице **Campaigns** нажать **Open in editor** у кампании из Keitaro или создать новую через **New campaign**.
2. **Fetch streams from KT** загружает потоки. Поток без офферов (редирект на Google) показывается как есть.
3. Добавить оффер — поиск по названию или ID в поле под таблицей, затем **Add**.
4. Изменения не уходят в Keitaro сразу: поток становится жёлтым, рядом с долей видно старое значение.
   **Push to KT** публикует поток, **Cancel** отменяет неопубликованные изменения.

Чтобы проверить синхронизацию в тестовом окружении, нажмите **View in KT**: откроется страница поддельного
Keitaro, где можно удалить оффер «прямо в Keitaro», а затем нажать **Fetch streams from KT** в редакторе.

## Логика редактора

У каждого оффера в потоке хранятся два состояния: черновик (то, что видно в интерфейсе) и опубликованное
(то, что сейчас в Keitaro). Поток «грязный» (жёлтый), если они различаются.

**Доли.** Доли — целые проценты, сумма активных офферов всегда 100. Удалённые офферы получают 0,
закреплённые сохраняют свою долю, остаток делится поровну между остальными. Если 100 не делится нацело,
лишние проценты по одному получают офферы, активированные последними:
3 оффера → 34/33/33, 4 → 25/25/25/25, один закреплён на 25 % → 38/37/25.
Пересчёт происходит при добавлении, удалении и возврате оффера, а также при ручной установке доли.

| Действие | Что происходит |
|---|---|
| Add | Оффер добавляется в поток, доли пересчитываются, поток жёлтый. Keitaro не меняется. |
| Remove | Оффер становится серым (removed, 0 %), доли пересчитываются. После Push оффер пропадает из Keitaro, но остаётся у нас в архиве. Оффер, ещё не опубликованный ни разу, удаляется сразу. |
| Bring back | Возвращает удалённый оффер, доли пересчитываются. После Push он снова в Keitaro. |
| Pin (значок булавки) | Фиксирует текущую долю оффера: при пересчётах она не меняется. |
| Клик по доле | Ручная установка доли: оффер закрепляется с этим значением, остальные пересчитываются. Закреплённые доли не могут в сумме превышать 100 %. |
| Push to KT | Отправляет офферы и доли в Keitaro (`PUT /streams/{id}`). Перед отправкой проверяется, что активные доли дают 100 %. |
| Cancel | Удаляет добавленные, но не опубликованные офферы и возвращает доли и статусы из Keitaro. |
| Fetch streams from KT | Синхронизация, Keitaro — источник истины. Офферы, которых больше нет в Keitaro, не удаляются, а становятся removed (их можно вернуть). Неопубликованные изменения при этом отбрасываются (интерфейс предупреждает). Доли из Keitaro берутся как есть, без пересчёта. |

Закрепление — локальная настройка интерфейса: в Keitaro оно не передаётся и Cancel его не сбрасывает.

## Структура

```
app/
├── main.py              # приложение FastAPI
├── configs/             # настройки: EnvSettings, классы по областям, готовые объекты, .env, .env_test
├── db.py, models.py     # SQLAlchemy: campaigns, streams, stream_offers
├── schemas.py           # схемы JSON API
├── keitaro/             # клиент Keitaro Admin API (http.py) и его интерфейс (base.py)
├── services/
│   ├── shares.py        # распределение долей
│   ├── editor.py        # синхронизация и операции редактора
│   └── creator.py       # создатель кампаний
├── routers/             # api.py (JSON API), pages.py (страницы)
├── templates/           # Jinja2
└── static/              # css/style.css, js/scripts.js
migrations/              # миграции Alembic
docker/                  # Dockerfile, docker-compose.yml (production), docker-compose-test.yml (тестовое окружение)
tests/
├── keitaro_service/     # поддельный Keitaro: app.py (Admin API + страница админки), store.py (данные),
│                        # seed_test_data.py (тестовые данные), settings.py, templates/, static/, test_service.py
└── test_*.py            # тесты приложения
```

## Тесты

```bash
pytest
```

Тесты не требуют Keitaro и Docker. Логика редактора и создателя кампаний проверяется по шагам видео
из задания через боевой HTTP-клиент, подключённый к поддельному Keitaro внутри процесса. Тесты сами
включают `APP_ENV=TEST`. В Docker: `docker compose -f docker/docker-compose-test.yml run --rm app pytest`.

По умолчанию тесты используют SQLite в памяти, поэтому запускаются без базы. Чтобы прогнать их на тестовой базе PostgreSQL (при каждом тесте её таблицы пересоздаются):

```bash
docker compose -f docker/docker-compose-test.yml up -d db-test
TEST_DATABASE_URL=postgresql+psycopg://adrobot:adrobot@localhost:5433/adrobot_test pytest
```

## Допущения

- Колонки Stats и Trends из исходного редактора не реализованы: в задании о статистике ничего не сказано.
- Имена полей Admin API (`schema`, `action_type`, `action_payload`, `filters`, `offers[].share`) взяты
  из открытых клиентов Keitaro; официальная документация доступна только в админке трекера.
- Если Keitaro вернёт ошибку посреди создания кампании, уже созданная часть останется в трекере —
  API Keitaro не поддерживает транзакции.
