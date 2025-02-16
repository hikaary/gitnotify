"""
Модуль для работы с HTTP запросами через aiohttp.
==================================================

Содержит обёртку для выполнения GET запросов, возврата JSON ответа и обработки ошибок.
"""

import logging

import aiohttp

session = None


async def get_json(
    url: str,
    headers: dict | None = None,
):
    """
    Выполняет GET запрос по указанному URL и возвращает данные в формате JSON.

    :param session: Используемая сессия aiohttp.
    :param url: URL для запроса.
    :param headers: HTTP заголовки, если необходимы.
    :return: Десериализованные данные из JSON или None в случае ошибки.
    """
    global session
    if not session:
        session = aiohttp.ClientSession()

    try:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                logging.error(
                    f'HTTP GET запрос по {url} вернул статус {response.status}'
                )
                return None
    except aiohttp.ClientError as e:
        logging.error(f'Ошибка HTTP GET запроса по {url}: {e}')
        return None
