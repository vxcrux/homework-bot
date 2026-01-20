import http
import logging
import os
import sys
import time
from logging import FileHandler, Formatter, StreamHandler

import requests
import telebot
from dotenv import load_dotenv
from telebot import TeleBot

import exceptions

load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
handler_file = FileHandler(filename="main.log")
handler_file.setLevel(logging.DEBUG)
logger.addHandler(handler)
logger.addHandler(handler_file)
formatter = Formatter(
    "%(asctime)s, %(levelname)s, %(message)s, %(funcName)s, %(lineno)s"
)
handler.setFormatter(formatter)

LAST_SENT_MESSAGE = None


def check_tokens():
    """Проверяем доступность переменных окружения."""
    missing_tokens = [
        token_name
        for token_name in (
            "PRACTICUM_TOKEN",
            "TELEGRAM_TOKEN",
            "TELEGRAM_CHAT_ID",
        )
        if not globals().get(token_name)
    ]

    if missing_tokens:
        error_message = f'Отсутствуют необходимые переменные окружения: {
            ", ".join(missing_tokens)
        }'
        logger.critical(error_message)
        sys.exit(error_message)

    logger.info("Все переменные окружения успешно загружены")


def send_message(bot, message):
    """Отправляет сообщения в чат."""
    global LAST_SENT_MESSAGE

    if message == LAST_SENT_MESSAGE:
        logger.debug(
            "Пропускаем отправку, сообщение идентично последнему отправленному"
        )
        return

    logger.debug(f'Начало отправки сообщения: "{message[:50]}..."')

    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug("Сообщение отправлено")

        LAST_SENT_MESSAGE = message

    except (telebot.apihelper.ApiException, requests.RequestException) as e:
        logger.error(f"Ошибка отправки сообщения: {e}")


def get_api_answer(timestamp):
    """Запрос к эндпоинту Яндекса."""
    params_request = {
        "url": ENDPOINT,
        "headers": HEADERS,
        "params": {"from_date": timestamp},
    }

    logger.debug(f"Начало запроса к API: {ENDPOINT} с from_date={timestamp}")

    try:
        response = requests.get(**params_request)
        if response.status_code != http.HTTPStatus.OK:
            status_reason = (
                response.reason if response.reason else "Неизвестная ошибка"
            )
            raise exceptions.InvalidRequest(
                f"Ошибка в получении запроса {response.status_code} ({status_reason})"
            )

        logger.info(f"Запрос к API успешен. Статус: {response.status_code}")
        return response.json()

    except (requests.ConnectionError, requests.RequestException) as e:
        error_detail = (
            f"Не удалось подключиться к API {ENDPOINT} с параметрами {timestamp}. "
            f"Ошибка: {e}"
        )
        logger.error(error_detail)
        raise exceptions.ResponseApiError(error_detail)


def check_response(response):
    """Проверяем ответ API."""
    logger.debug("Начало проверки ответа сервера.")
    if not isinstance(response, dict):
        raise TypeError(
            f"Запрос к API вернул ожидаемый тип dict, но получен {type(response)}"
        )

    if "homeworks" not in response:
        raise exceptions.EmptyResponseAPI("Нет ключа homeworks")

    homeworks = response.get("homeworks")

    if not isinstance(homeworks, list):
        raise TypeError(
            f'Значение ключа "homeworks" должно быть list, получен {type(homeworks)}'
        )

    logger.info("Проверка структуры ответа API завершена успешно")
    return homeworks


def parse_status(homework):
    """Получаем статус последней домашней работы."""
    logger.debug("Начало проверки статуса отдельной работы")

    if "homework_name" not in homework:
        raise exceptions.UnknownStatus("Нет homework_name в homework")

    homework_name = homework.get("homework_name")
    homework_status = homework.get("status")

    if homework_status not in HOMEWORK_VERDICTS:
        raise exceptions.UnknownStatus(
            f'Неизвестный статус работы "{homework_status}" для работы {homework_name}'
        )

    verdict = HOMEWORK_VERDICTS[homework_status]

    final_message = (
        f'Изменился статус проверки работы "{homework_name}". {verdict}'
    )
    logger.debug(f"Статус успешно получен: {final_message}")
    return final_message


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    send_message(bot, "Старт")

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            current_date = response.get("current_date")
            if current_date:
                timestamp = current_date
            else:
                timestamp = int(time.time())

            if homeworks:
                status_message = parse_status(homeworks[0])
                send_message(bot, status_message)
            else:
                logger.debug("Новых работ нет")

        except (
            exceptions.InvalidRequest,
            exceptions.ResponseApiError,
            exceptions.EmptyResponseAPI,
            exceptions.UnknownStatus,
            TypeError,
        ) as error:
            message = f"Сбой в работе программы: {error}"
            logger.error(message)
            send_message(bot, message)
        except Exception as error:
            message = f"Критический сбой в работе программы: {error}"
            logger.critical(message, exc_info=True)
            send_message(bot, message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
