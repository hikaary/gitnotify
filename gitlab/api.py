"""
Модуль для работы с API GitLab.
===============================

Содержит функции для получения списка проектов, статусов пайплайнов, merge request
и событий, используя обёртку для HTTP запросов из модуля http_client.
"""

import logging
from typing import TypedDict

from .http_client import get_json


class GitlabConfig(TypedDict, total=False):
    poll_interval: int | float
    url: str
    token: str


class Project(TypedDict, total=False):
    id: int
    name: str


class Pipeline(TypedDict):
    id: int
    status: str


class MergeRequestAuthor(TypedDict):
    username: str


class MergeRequest(TypedDict, total=False):
    id: int
    title: str
    state: str
    iid: int
    author: MergeRequestAuthor


class PushData(TypedDict, total=False):
    ref: str
    commit_count: int
    author_username: str


class RawEvent(TypedDict, total=False):
    id: int
    push_data: PushData
    author_username: str


async def fetch_all_projects(
    base_url: str,
    token: str,
) -> list[Project] | None:
    """
    Получает список проектов, доступных пользователю, через GitLab API.

    :param base_url: Базовый URL GitLab.
    :param token: Персональный токен для доступа к API GitLab.
    :return: Список проектов в формате JSON или None.
    """
    url = f'{base_url}/api/v4/projects?membership=true&per_page=100'
    headers = {'PRIVATE-TOKEN': token}
    projects = await get_json(url, headers)
    if projects is None:
        logging.error('Не удалось получить список проектов.')
    return projects


async def fetch_pipeline(
    project_id: int,
    base_url: str,
    token: str,
) -> Pipeline | None:
    """
    Получает последний пайплайн для заданного проекта.

    :param project_id: Идентификатор проекта.
    :param base_url: Базовый URL GitLab.
    :param token: Персональный токен для доступа к API GitLab.
    :return: Данные последнего пайплайна или None.
    """
    url = f'{base_url}/api/v4/projects/{project_id}/pipelines?per_page=1'
    headers = {'PRIVATE-TOKEN': token}
    pipelines: list[Pipeline] | None = await get_json(url, headers)
    if pipelines and len(pipelines) > 0:
        return pipelines[0]
    return None


async def fetch_merge_requests(
    project_id: int,
    base_url: str,
    token: str,
    per_page: int = 5,
) -> list[MergeRequest] | None:
    """
    Получает список merge request для заданного проекта.

    :param project_id: Идентификатор проекта.
    :param base_url: Базовый URL GitLab.
    :param token: Персональный токен для доступа к API GitLab.
    :param per_page: Количество MR для выборки.
    :return: Список merge request в формате JSON или None.
    """
    url = (
        f'{base_url}/api/v4/projects/{project_id}/merge_requests?'
        f'state=all&order_by=updated_at&sort=desc&per_page={per_page}'
    )
    headers = {'PRIVATE-TOKEN': token}
    mrs: list[MergeRequest] | None = await get_json(url, headers)
    if mrs is None:
        logging.error(
            f'Не удалось получить merge requests для проекта {project_id}.'
        )
    return mrs


async def fetch_project_events(
    project_id: int,
    base_url: str,
    token: str,
    per_page: int = 5,
) -> list[RawEvent] | None:
    """
    Получает список событий для заданного проекта через GitLab API.

    :param project_id: Идентификатор проекта.
    :param base_url: Базовый URL GitLab.
    :param token: Персональный токен для доступа к API GitLab.
    :param per_page: Количество событий для выборки.
    :return: Список событий в формате JSON или None.
    """
    url = f'{base_url}/api/v4/projects/{project_id}/events?per_page={per_page}'
    headers = {'PRIVATE-TOKEN': token}
    events_list: list[RawEvent] | None = await get_json(url, headers)
    if events_list is None:
        logging.error(f'Не удалось получить события для проекта {project_id}.')
    return events_list
