GitNotify - Мониторинг GitLab и Telegram-бот
============================================

Описание
--------
GitNotify – это система мониторинга событий GitLab, которая состоит из двух основных компонентов:

1. **gitlab_monitor.py**  
   Асинхронный скрипт для периодической проверки статусов CI/CD пайплайнов. При обнаружении изменения статуса скрипт может выполнять заданные действия (например, отправлять системные уведомления).

2. **Telegram-бот** (telegram_bot.py)  
   Асинхронный бот, реализованный на основе библиотеки *aiogram* (версия 3.x), который опрашивает события GitLab, такие как:
   - Изменения в статусах CI/CD пайплайнов,
   - Push-события (с информацией о ветке, количестве коммитов и авторе),
   - События merge request (создание, обновление, закрытие).

При обнаружении событий бот отправляет уведомления в Telegram согласно настройкам и шаблонам, заданным в файле конфигурации **config.toml**. Если для проекта настроен пинг через *repo_mapping*, бот дополнительно отправляет отдельное сообщение с упоминанием нужного пользователя. Для формирования уведомлений используется название репозитория (project_name), а идентификатор может выводиться в скобках, если это необходимо.

Структура проекта
-----------------
.. code-block:: text

    .
    ├── .gitignore
    ├── config.toml                # Файл конфигурации (настройки GitLab, Telegram и шаблоны уведомлений)
    ├── gitlab
    │   ├── __init__.py
    │   ├── api.py                 # Модуль для работы с API GitLab:
    │   │         - Получение списка проектов, статусов пайплайнов и другой информации.
    │   ├── events.py              # Модуль для опроса событий GitLab (CI/CD, push, merge request)
    │   └── http_client.py         # Модуль для работы с HTTP запросами через aiohttp.
    ├── gitlab_monitor.py          # Скрипт для мониторинга CI/CD пайплайнов (с использованием aiohttp)
    ├── pyproject.toml             # Файл настроек проекта (при необходимости)
    ├── README.md                  # Документация проекта (этот файл)
    └── telegram_bot.py            # Главный модуль Telegram-бота (опрашивает события и отправляет уведомления)

Установка
---------
Для работы с проектом необходим Python 3.12. Рекомендуется использовать виртуальное окружение.

Установка зависимостей производится через утилиту **uv**:

.. code-block:: bash

    uv add aiohttp aiogram tomllib

Конфигурация
------------
Все настройки проекта задаются в файле **config.toml**. Пример конфигурации:

.. code-block:: toml

    [gitlab]
    url = "https://gitlab.com"
    token = "YOUR_GITLAB_TOKEN"
    poll_interval = 5
    # Пустой список проектов означает, что список будет получен автоматически через API
    projects = []

    [telegram]
    token = "YOUR_TELEGRAM_BOT_TOKEN"
    default_chat = 123456789
    # Шаблоны уведомлений (HTML формат)
    pipeline_template = """
    <b>CI/CD обновление: {project_name}</b>
    Пользователь: GitLab
    Время: {timestamp}
    Действие: {description}
    Ссылка: <a href="{base_url}/projects/{project_id}">{project_name}</a>
    """
    push_template = """
    <b>Push событие: {project_name}</b>
    Пользователь: {author}
    Время: {timestamp}
    Действие: Push в ветку {branch}, коммитов: {commit_count}
    Ссылка: <a href="{base_url}/projects/{project_id}">{project_name}</a>
    """
    mr_template = """
    <b>Merge Request: {project_name}</b>
    Пользователь: {author}
    Время: {timestamp}
    Действие: {title} (состояние: {state})
    Ссылка: <a href="{base_url}/projects/{project_id}/merge_requests/{iid}">MR #{iid}</a>
    """
    # Привязка репозитория к тегу для пинга
    repo_mapping = {
      "project_123456": "@telegram_nick1",
      "project_789012": "@telegram_nick2"
    }

Запуск
------
Для запуска системы необходимо выполнить два процесса:

1. **GitLab мониторинг**  
   Запустите скрипт для проверки статусов пайплайнов:

.. code-block:: bash

    python3 gitlab_monitor.py

2. **Telegram-бот**  
   Запустите Telegram-бот:

.. code-block:: bash

    python3 telegram_bot.py

При запуске оба процесса будут работать асинхронно, опрашивая GitLab и отправляя уведомления по событиям.

Зависимости
-----------
Проект использует следующие библиотеки:
- **aiohttp** – для выполнения асинхронных HTTP-запросов к GitLab API.
- **aiogram** – для реализации Telegram-бота (версия 3.x).
- **tomllib** – для чтения настроек из файла TOML (встроенная библиотека Python 3.11+).

Лицензия
--------
Этот проект распространяется под лицензией MIT. Подробности см. в файле LICENSE.
