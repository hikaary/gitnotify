#!/usr/bin/env python3
"""
Монитор GitLab CI/CD пайплайнов.
==================================

Этот скрипт опрашивает GitLab API для получения статусов CI/CD пайплайнов.
При обнаружении изменения статуса пайплайна отправляется уведомление с использованием
названия проекта, а не только его идентификатора.

Конфигурация:
  Чтение параметров производится из файла config.toml.
  В секции [gitlab] задаются:
      url           - URL GitLab (например, "https://gitlab.com")
      token         - персональный токен для доступа к API GitLab
      poll_interval - интервал опроса (в секундах)

При каждом опросе список проектов получается через API.
Для каждого проекта извлекается его идентификатор и название (project_name).
Если статус последнего пайплайна изменился, уведомление включает название проекта.

Зависимости:
  Python 3.12, aiohttp, tomllib.
"""

import asyncio
import logging
import sys

import aiohttp
import tomllib

from gitlab import api

CONFIG_FILE = 'config.toml'


async def load_config():
    """
    Загружает конфигурацию из TOML файла.

    :return: Словарь с параметрами конфигурации.
    """
    try:
        with open(CONFIG_FILE, 'rb') as f:
            return tomllib.load(f)
    except FileNotFoundError:
        print(f'Файл конфигурации {CONFIG_FILE} не найден.', file=sys.stderr)
        sys.exit(1)
    except tomllib.TOMLDecodeError as e:
        print(f'Ошибка разбора TOML: {e}', file=sys.stderr)
        sys.exit(1)


async def monitor():
    """
    Основная функция мониторинга пайплайнов.
    На каждом цикле выполняется запрос для получения списка проектов через API GitLab.
    Для каждого проекта определяется статус последнего пайплайна.
    Если статус изменился с предыдущего опроса, отправляется уведомление, включающее название проекта.
    """
    config = await load_config()
    gitlab_conf = config.get('gitlab', {})
    base_url = gitlab_conf.get('url', 'https://gitlab.com')
    token = gitlab_conf.get('token', '')
    poll_interval = gitlab_conf.get('poll_interval', 5)

    if not token:
        print('Токен GitLab не задан в конфигурации.', file=sys.stderr)
        sys.exit(1)

    previous_status = {}

    while True:
        await asyncio.sleep(poll_interval)
        projects = await api.fetch_all_projects(base_url, token)
        if projects is None:
            await asyncio.sleep(poll_interval)
            continue

        for project in projects:
            project_id = project.get('id')
            project_name = project.get('name', f'Проект {project_id}')
            pipeline = await api.fetch_pipeline(project_id, base_url, token)
            if pipeline is None:
                continue
            pipeline_id = pipeline.get('id')
            status = pipeline.get('status')
            prev = previous_status.get(project_id)
            if prev is None:
                previous_status[project_id] = {
                    'id': pipeline_id,
                    'status': status,
                    'name': project_name,
                }
            elif prev['id'] != pipeline_id or prev['status'] != status:
                previous_status[project_id] = {
                    'id': pipeline_id,
                    'status': status,
                    'name': project_name,
                }
                title = f'Пайплайн проекта {project_name}'
                if status == 'success':
                    message = (
                        f'Пайплайн проекта {project_name} завершён успешно.'
                    )
                elif status == 'failed':
                    message = (
                        f'Пайплайн проекта {project_name} завершился с ошибкой.'
                    )
                else:
                    message = f'Новый статус пайплайна проекта {project_name}: {status}'
                logging.info(f'{title}: {message}')


def main():
    """
    Точка входа в скрипт.
    """
    try:
        asyncio.run(monitor())
    except KeyboardInterrupt:
        print('Мониторинг остановлен пользователем.', file=sys.stderr)
    except aiohttp.ClientError as e:
        print(f'Ошибка работы сети: {e}', file=sys.stderr)


if __name__ == '__main__':
    main()
