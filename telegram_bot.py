#!/usr/bin/env python3
"""
Telegram-бот для мониторинга событий GitLab.
============================================

Этот скрипт использует функции из пакета gitlab для опроса событий:
  - CI/CD пайплайнов,
  - push-событий,
  - merge request.

При обнаружении события бот отправляет уведомление в Telegram согласно шаблонам,
заданным в файле конфигурации config.toml. Если для проекта задан пинг в секции
repo_mapping, уведомление будет дополнительно сопровождаться отдельным сообщением с пингом.

Конфигурация:
  Параметры задаются в файле config.toml, содержащем секции [gitlab] и [telegram].
  Доступные шаблоны:
    * pipeline_template для CI/CD событий,
    * push_template для push-событий,
    * mr_template для Merge Request.
  Также используется repo_mapping для привязки проекта к тегу.
"""

import asyncio
import logging
import sys

import tomllib
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from gitlab import events

CONFIG_FILE = 'config.toml'


async def load_config():
    """
    Загружает конфигурацию из TOML файла.

    :return: Словарь с настройками.
    """
    try:
        with open(CONFIG_FILE, 'rb') as f:
            return tomllib.load(f)
    except Exception as e:
        logging.error(f'Ошибка загрузки конфигурации: {e}')
        sys.exit(1)


async def telegram_notification_callback(
    event,
    bot,
    telegram_conf,
    gitlab_conf,
):
    """
    Callback для отправки уведомлений в Telegram. Формирует уведомление,
    используя шаблоны из конфигурации, и дополнительно отправляет пинг, если для
    проекта задан соответствующий тег в repo_mapping.

    Для уведомлений используется название репозитория (project_name).

    :param event: Словарь с данными события.
    :param bot: Экземпляр Telegram-бота.
    :param telegram_conf: Секция конфигурации [telegram] из config.toml.
    :param gitlab_conf: Секция конфигурации [gitlab] из config.toml.
    """
    base_url = gitlab_conf.get('url', 'https://gitlab.com')
    project_id = event.get('project_id')
    project_name = event.get('project_name', f'Проект {project_id}')
    repo_mapping = telegram_conf.get('repo_mapping', {})
    ping = ''
    for mention, projects in repo_mapping:
        if project_name in projects:
            ping += mention

    event_type = event.get('type')
    if event_type == 'pipeline':
        status = event.get('status')
        if status == 'success':
            description = 'Пайплайн завершён успешно.'
        elif status == 'failed':
            description = 'Пайплайн завершился с ошибкой.'
        else:
            description = f'Новый статус: {status}'
        template = telegram_conf.get('pipeline_template')
        if not template:
            template = (
                '<b>CI/CD обновление: {project_name}</b>\n'
                'Пользователь: GitLab\n'
                'Время: {timestamp}\n'
                '{description}\n'
                'Ссылка: <a href="{base_url}/projects/{project_id}">{project_name}</a>'
            )
        data = {
            'project_id': project_id,
            'project_name': project_name,
            'timestamp': event.get('timestamp'),
            'description': description,
            'base_url': base_url,
        }
    elif event_type == 'push':
        branch = event.get('branch')
        commit_count = event.get('commit_count')
        author = event.get('author', 'GitLab')
        template = telegram_conf.get('push_template')
        if not template:
            template = (
                '<b>Push событие: {project_name}</b>\n'
                'Пользователь: {author}\n'
                'Время: {timestamp}\n'
                'Действие: Push в ветку {branch}, коммитов: {commit_count}\n'
                'Ссылка: <a href="{base_url}/projects/{project_id}">{project_name}</a>'
            )
        data = {
            'project_id': project_id,
            'project_name': project_name,
            'branch': branch,
            'commit_count': commit_count,
            'timestamp': event.get('timestamp'),
            'author': author,
            'base_url': base_url,
        }
    elif event_type == 'merge_request':
        state = event.get('state')
        title_mr = event.get('title', 'Merge Request')
        iid = event.get('iid')
        author = event.get('author', 'GitLab')
        template = telegram_conf.get('mr_template')
        if not template:
            template = (
                '<b>Merge Request: {project_name}</b>\n'
                'Пользователь: {author}\n'
                'Время: {timestamp}\n'
                'Действие: {title} (состояние: {state})\n'
                'Ссылка: <a href="{base_url}/projects/{project_id}/merge_requests/{iid}">MR #{iid}</a>'
            )
        data = {
            'project_id': project_id,
            'project_name': project_name,
            'state': state,
            'title': title_mr,
            'timestamp': event.get('timestamp'),
            'base_url': base_url,
            'iid': iid,
            'author': author,
        }
    else:
        template = telegram_conf.get('message_template')
        if not template:
            template = '<b>GitLab событие</b>\nДанные: {event}'
        data = {'event': event}

    data['ping'] = ping
    try:
        text = template.format(**data)
    except KeyError as e:
        text = f'Ошибка формирования сообщения: отсутствует ключ {e}'
    try:
        await bot.send_message(
            telegram_conf.get('default_chat'),
            text,
            parse_mode=ParseMode.HTML,
            message_thread_id=telegram_conf.get('message_thread_id'),
        )
    except Exception as e:
        logging.error(f'Ошибка отправки уведомления в Telegram: {e}')


async def start_polling(bot, telegram_conf, gitlab_conf):
    """
    Запускает фоновые задачи для опроса событий GitLab и отправки уведомлений в Telegram.
    """

    async def callback(event):
        await telegram_notification_callback(
            event,
            bot,
            telegram_conf,
            gitlab_conf,
        )

    await asyncio.gather(
        events.poll_pipeline_events(callback, gitlab_conf),
        events.poll_push_events(callback, gitlab_conf),
        events.poll_mr_events(callback, gitlab_conf),
    )


async def main():
    logging.basicConfig(level=logging.INFO)
    config = await load_config()
    telegram_conf = config.get('telegram', {})
    gitlab_conf = config.get('gitlab', {})

    bot_token = telegram_conf.get('token')
    if not bot_token:
        print('Токен Telegram не задан в конфигурации.', file=sys.stderr)
        sys.exit(1)

    bot = Bot(
        token=bot_token,
        default_bot_properties=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    asyncio.create_task(start_polling(bot, telegram_conf, gitlab_conf))
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info('Telegram бот остановлен пользователем.')
