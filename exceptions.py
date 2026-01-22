class InvalidRequest(Exception):
    """Ошибка в получении запроса."""

    pass


class EmptyResponseAPI(Exception):
    """Пустой ответ API."""

    pass


class UnknownStatus(Exception):
    """Hеизвестный статус домашней работы."""

    pass
