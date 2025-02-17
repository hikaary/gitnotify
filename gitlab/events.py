"""
Модуль для опроса событий GitLab.
=================================

Содержит функции для периодического опроса событий GitLab (CI/CD пайплайнов,
push-событий и merge request) с использованием функций из модуля gitlab/api.py.

Каждая функция принимает callback, которая вызывается при обнаружении нового
или изменённого события. Список проектов получается автоматически через функцию
fetch_all_projects, что позволяет работать со всеми доступными проектами и избегать
уведомлений о старых событиях при запуске.
"""

import asyncio
from time import localtime, strftime
from typing import Awaitable, Callable, TypedDict, Union

from gitlab import api


class PipelineEvent(TypedDict):
    type: str
    project_id: int
    project_name: str
    pipeline_id: int
    status: str
    timestamp: str


class PushEvent(TypedDict):
    type: str
    project_id: int
    project_name: str
    event_id: int
    branch: str
    commit_count: int
    timestamp: str
    author: str


class MergeRequestEvent(TypedDict):
    type: str
    project_id: int
    project_name: str
    mr_id: int
    state: str
    title: str
    timestamp: str
    author: str
    iid: int


type Event = Union[PipelineEvent, PushEvent, MergeRequestEvent]
type Callback = Callable[[Event], Awaitable[None]]


async def poll_pipeline_events(
    callback: Callback,
    gitlab_conf: api.GitlabConfig,
) -> None:
    """
    Опрос CI/CD пайплайнов для всех проектов GitLab.
    Вызывает callback при обнаружении нового или изменённого пайплайна.
    """
    previous_status: dict[int, api.Pipeline] = {}
    first_run = True
    poll_interval = gitlab_conf.get('poll_interval', 5)
    base_url = gitlab_conf.get('url', 'https://gitlab.com')
    token = gitlab_conf.get('token', '')

    while True:
        await asyncio.sleep(poll_interval)
        projects = await api.fetch_all_projects(
            base_url,
            token,
        )
        if not projects:
            continue
        for project in projects:
            project_id = project['id']
            project_name = project['name']
            pipeline = await api.fetch_pipeline(project_id, base_url, token)
            if not pipeline:
                continue
            pipeline_id = pipeline['id']
            status = pipeline['status']
            prev = previous_status.get(project_id)
            if prev is None:
                previous_status[project_id] = api.Pipeline(
                    id=pipeline_id,
                    status=status,
                )
                continue
            if prev['id'] != pipeline_id or prev['status'] != status:
                previous_status[project_id] = api.Pipeline(
                    id=pipeline_id,
                    status=status,
                )
                if not first_run:
                    event: PipelineEvent = {
                        'type': 'pipeline',
                        'project_id': project_id,
                        'project_name': project_name,
                        'pipeline_id': pipeline_id,
                        'status': status,
                        'timestamp': strftime('%Y-%m-%d %H:%M:%S', localtime()),
                    }
                    await callback(event)
        first_run = False


async def poll_push_events(
    callback: Callback,
    gitlab_conf: api.GitlabConfig,
) -> None:
    """
    Опрос push-событий для всех проектов GitLab.
    Вызывает callback при обнаружении нового события.
    """
    previous_push: dict[int, int] = {}
    first_run = True
    poll_interval = gitlab_conf.get('poll_interval', 5)
    base_url = gitlab_conf.get('url', 'https://gitlab.com')
    token = gitlab_conf.get('token', '')

    while True:
        await asyncio.sleep(poll_interval)
        projects = await api.fetch_all_projects(
            base_url,
            token,
        )
        if not projects:
            continue
        for project in projects:
            project_id = project['id']
            project_name = project['name']
            events_list = await api.fetch_project_events(
                project_id,
                base_url,
                token,
            )
            if not events_list:
                continue

            push_events = [event for event in events_list if event['push_data']]
            if not push_events:
                continue

            latest_push = push_events[0]
            event_id = latest_push['id']
            prev_id = previous_push.get(project_id)
            if prev_id is None:
                previous_push[project_id] = event_id
                continue
            if event_id != prev_id:
                previous_push[project_id] = event_id
                push_data = latest_push['push_data']
                branch = push_data['ref']
                commit_count = push_data['commit_count']
                if not first_run:
                    event: PushEvent = {
                        'type': 'push',
                        'project_id': project_id,
                        'project_name': project_name,
                        'event_id': event_id,
                        'branch': branch,
                        'commit_count': commit_count,
                        'timestamp': strftime('%Y-%m-%d %H:%M:%S', localtime()),
                        'author': latest_push['author_username'],
                    }
                    await callback(event)
        first_run = False


async def poll_mr_events(
    callback: Callback,
    gitlab_conf: api.GitlabConfig,
) -> None:
    """
    Опрос событий merge request для всех проектов GitLab.
    Вызывает callback при обнаружении нового или изменённого MR.
    """
    previous_mr: dict[int, dict[int, str]] = {}
    first_run = True
    poll_interval = gitlab_conf.get('poll_interval', 5)
    base_url = gitlab_conf.get('url', 'https://gitlab.com')
    token = gitlab_conf.get('token', '')

    while True:
        await asyncio.sleep(poll_interval)
        projects = await api.fetch_all_projects(
            base_url,
            token,
        )
        if not projects:
            continue
        for project in projects:
            project_id = project['id']
            project_name = project['name']
            mrs = await api.fetch_merge_requests(project_id, base_url, token)
            if not mrs:
                continue

            latest_mr = mrs[0]
            mr_id = latest_mr['id']
            current_state = latest_mr['state']
            prev_state = previous_mr.get(project_id, {}).get(mr_id)
            if prev_state is None:
                previous_mr.setdefault(project_id, {})[mr_id] = current_state
                continue
            if prev_state != current_state:
                previous_mr.setdefault(project_id, {})[mr_id] = current_state
                if not first_run:
                    event: MergeRequestEvent = {
                        'type': 'merge_request',
                        'project_id': project_id,
                        'project_name': project_name,
                        'mr_id': mr_id,
                        'state': current_state,
                        'title': latest_mr.get('title', ''),
                        'timestamp': strftime('%Y-%m-%d %H:%M:%S', localtime()),
                        'author': latest_mr['author']['username'],
                        'iid': latest_mr.get('iid', 0),
                    }
                    await callback(event)
        first_run = False
