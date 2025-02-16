"""
Модуль для опроса событий GitLab.
=================================

Содержит функции для периодического опроса событий GitLab (CI/CD пайплайнов,
push-событий и merge request) с использованием функций из модуля gitlab/api.py.

Каждая функция принимает callback, которая вызывается при обнаружении нового
или изменённого события. Теперь список проектов получается автоматически через
функцию fetch_all_projects, что позволяет работать со всеми проектами, доступными
пользователю, а также предотвращается отправка уведомлений для старых событий при запуске.
"""

import asyncio
from time import localtime, strftime

from gitlab import api

from .http_client import get_json


async def poll_pipeline_events(callback, gitlab_conf):
    """
    Периодически опрашивает CI/CD пайплайны для всех проектов, полученных из GitLab.
    При обнаружении нового пайплайна или изменении его статуса вызывает callback
    с данными события.

    :param callback: Функция, принимающая один аргумент – словарь события.
    :param gitlab_conf: Секция конфигурации GitLab из файла config.toml.
    """
    previous_status = {}
    first_run = True
    poll_interval = gitlab_conf.get('poll_interval', 5)
    base_url = gitlab_conf.get('url', 'https://gitlab.com')
    token = gitlab_conf.get('token', '')

    while True:
        await asyncio.sleep(poll_interval)
        projects = await api.fetch_all_projects(base_url, token)
        for project in projects:
            project_id = project.get('id')
            project_name = project.get('name', f'Project {project_id}')
            pipeline = await api.fetch_pipeline(
                project_id,
                base_url,
                token,
            )
            if not pipeline:
                continue
            pipeline_id = pipeline.get('id')
            status = pipeline.get('status')
            prev = previous_status.get(project_id)
            if prev is None:
                previous_status[project_id] = {
                    'id': pipeline_id,
                    'status': status,
                }
                continue
            elif prev['id'] != pipeline_id or prev['status'] != status:
                previous_status[project_id] = {
                    'id': pipeline_id,
                    'status': status,
                }
                if not first_run:
                    event = {
                        'type': 'pipeline',
                        'project_id': project_id,
                        'project_name': project_name,
                        'pipeline_id': pipeline_id,
                        'status': status,
                        'timestamp': strftime('%Y-%m-%d %H:%M:%S', localtime()),
                    }
                    await callback(event)
        first_run = False


async def poll_push_events(callback, gitlab_conf):
    """
    Периодически опрашивает push-события для всех проектов, полученных из GitLab.
    При обнаружении нового события вызывает callback с данными события.

    :param callback: Функция, принимающая один аргумент – словарь события.
    :param gitlab_conf: Секция конфигурации GitLab.
    """
    previous_push = {}
    first_run = True
    poll_interval = gitlab_conf.get('poll_interval', 5)
    base_url = gitlab_conf.get('url', 'https://gitlab.com')
    token = gitlab_conf.get('token', '')

    while True:
        await asyncio.sleep(poll_interval)
        projects = await api.fetch_all_projects(base_url, token)
        for project in projects:
            project_id = project.get('id')
            project_name = project.get('name', f'Project {project_id}')
            headers = {'PRIVATE-TOKEN': token}
            url = f'{base_url}/api/v4/projects/{project_id}/events?per_page=5'
            events_list = await get_json(url, headers)
            if not events_list:
                continue

            push_events = [
                event for event in events_list if event.get('push_data')
            ]
            if not push_events:
                continue

            latest_push = push_events[0]
            event_id = latest_push.get('id')
            prev_id = previous_push.get(project_id)
            if prev_id is None:
                previous_push[project_id] = event_id
                continue
            if event_id != prev_id:
                previous_push[project_id] = event_id
                push_data = latest_push.get('push_data', {})
                branch = push_data.get('ref', 'Неизвестно')
                commit_count = push_data.get('commit_count', 0)
                if not first_run:
                    event = {
                        'type': 'push',
                        'project_id': project_id,
                        'project_name': project_name,
                        'event_id': event_id,
                        'branch': branch,
                        'commit_count': commit_count,
                        'timestamp': strftime('%Y-%m-%d %H:%M:%S', localtime()),
                        'author': latest_push.get('author_username', 'GitLab'),
                    }
                    await callback(event)
        first_run = False


async def poll_mr_events(callback, gitlab_conf):
    """
    Периодически опрашивает события merge request для всех проектов, полученных из GitLab.
    При обнаружении нового или изменённого MR вызывает callback с данными события.

    :param callback: Функция, принимающая один аргумент – словарь события.
    :param gitlab_conf: Секция конфигурации GitLab.
    """
    previous_mr = {}
    first_run = True
    poll_interval = gitlab_conf.get('poll_interval', 5)
    base_url = gitlab_conf.get('url', 'https://gitlab.com')
    token = gitlab_conf.get('token', '')

    while True:
        await asyncio.sleep(poll_interval)
        projects = await api.fetch_all_projects(base_url, token)
        for project in projects:
            project_id = project.get('id')
            project_name = project.get('name', f'Project {project_id}')
            headers = {'PRIVATE-TOKEN': token}
            url = f'{base_url}/api/v4/projects/{project_id}/merge_requests?state=all&order_by=updated_at&sort=desc&per_page=5'
            mrs = await get_json(url, headers)
            if not mrs:
                continue

            latest_mr = mrs[0]
            mr_id = latest_mr.get('id')
            current_state = latest_mr.get('state')
            prev_state = previous_mr.get(project_id, {}).get(mr_id)
            if prev_state is None:
                previous_mr.setdefault(project_id, {})[mr_id] = current_state
                continue
            if prev_state != current_state:
                previous_mr.setdefault(project_id, {})[mr_id] = current_state
                if not first_run:
                    event = {
                        'type': 'merge_request',
                        'project_id': project_id,
                        'project_name': project_name,
                        'mr_id': mr_id,
                        'state': current_state,
                        'title': latest_mr.get('title', ''),
                        'timestamp': strftime('%Y-%m-%d %H:%M:%S', localtime()),
                        'author': latest_mr.get('author', {}).get(
                            'username', 'GitLab'
                        ),
                        'iid': latest_mr.get('iid'),
                    }
                    await callback(event)
        first_run = False
