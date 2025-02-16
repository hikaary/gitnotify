"""
Модуль для работы с API GitLab.
===============================

Содержит функции для получения списка проектов, статусов пайплайнов и другой информации,
используя обёртку для HTTP запросов из модуля http_client.
"""

import logging

from .http_client import get_json


async def fetch_all_projects(base_url: str, token: str):
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
):
    """
    Получает последний пайплайн для заданного проекта.

    :param project_id: Идентификатор проекта.
    :param base_url: Базовый URL GitLab.
    :param token: Персональный токен для доступа к API GitLab.
    :return: Данные последнего пайплайна или None.
    """
    url = f'{base_url}/api/v4/projects/{project_id}/pipelines?per_page=1'
    headers = {'PRIVATE-TOKEN': token}
    pipelines = await get_json(url, headers)
    if pipelines and len(pipelines) > 0:
        return pipelines[0]
    else:
        return None


async def fetch_merge_requests(
    project_id: int,
    base_url: str,
    token: str,
    per_page: int = 5,
):
    """
    Получает список merge request для заданного проекта.

    :param project_id: Идентификатор проекта.
    :param base_url: Базовый URL GitLab.
    :param token: Персональный токен для доступа к API GitLab.
    :param per_page: Количество MR для выборки.
    :return: Список merge request в формате JSON или None.
    """
    url = f'{base_url}/api/v4/projects/{project_id}/merge_requests?state=all&order_by=updated_at&sort=desc&per_page={per_page}'
    headers = {'PRIVATE-TOKEN': token}
    mrs = await get_json(url, headers)
    if mrs is None:
        logging.error(
            f'Не удалось получить merge requests для проекта {project_id}.'
        )
    return mrs
