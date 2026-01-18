class InvalidRequest(Exception):
    """Ошибка в получении запроса."""

    pass


class ResponseApiError(Exception):
    """Ошибка соединения с API."""

    pass


class EmptyResponseAPI(Exception):
    """Пустой ответ API."""

    pass


class UnknownStatus(Exception):
    """Hеизвестный статус домашней работы."""

    pass
