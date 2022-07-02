import logging
import os
import sys
import time

from http import HTTPStatus
from logging.handlers import RotatingFileHandler
from urllib.error import HTTPError

import requests
import telegram

from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
FOLDER_LOG = __file__ + '.log'


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

SEND_MESSAGE = 'Send message: {message}'
ERROR_TELEGRAMM = 'Failed to send message! Error: {error}'
ERROR_REQUEST_HTTP = 'Http Error: {error}'
ERROR_CONNECTING = 'Error Connecting : {error}'
RESPONSE_UNEXPECTED = ('Unexpected response from the server. Error: {error}'
                       'API response: {status}')
ERROR_REPONSE = 'Unexpected response from the server. API response: {status}'
ERROR_KEY = 'No key: {type}}'
HOMEWORK_TYPE = 'Homework not a type: {type}'
UNDOCUMENDED_STATUS = 'Undocumented status of homework: {homework_status}'
STATUS_CHANGED = 'Изменился статус проверки работы "{homework_name}".{verdict}'
ERROR_PROJECT = 'Сбой в работе программы: {error}'
ERROR_TOKENS = 'Required variable missing: {name}'
NO_NEW_CHECKS = 'No new checks in homeworks'
TOKENS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
console_log = logging.StreamHandler(sys.stdout)
logger.addHandler(console_log)
handler = RotatingFileHandler(
    FOLDER_LOG, maxBytes=50000000, backupCount=5
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(SEND_MESSAGE.format(message=message))
    except telegram.TelegramError as error:
        logger.error(ERROR_TELEGRAMM.format(error=error), exc_info=True)
        return error


def get_api_answer(timestamp):
    """Запрос к API."""
    request = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    try:
        response_statuses = requests.get(**request)
    except requests.exceptions.HTTPError as http_err:
        raise HTTPError(ERROR_REQUEST_HTTP.format(
            **request, error=http_err))
    except requests.exceptions.RequestException as connect_err:
        raise ConnectionError(ERROR_CONNECTING.format(
            **request, error=connect_err))
    statuses = response_statuses.json()
    for field in ['error', 'code']:
        if field in statuses:
            raise RuntimeError(
                RESPONSE_UNEXPECTED.format(
                    **request, error=statuses.get(field),
                    status=response_statuses.status_code))
    if response_statuses.status_code != HTTPStatus.OK.value:
        raise ValueError(ERROR_REPONSE.format(
            **request, status=response_statuses.status_code))
    logger.debug(statuses)
    return statuses


def check_response(response):
    """Проверка API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(HOMEWORK_TYPE)
    try:
        homework = response['homeworks']
    except KeyError as error:
        raise error(ERROR_KEY).format(type=type(response))
    if not isinstance(homework, list):
        raise TypeError(HOMEWORK_TYPE.format(type=type(homework)))
    logger.debug(homework)
    return homework


def parse_status(homework):
    """Сообщение с информацией о ревью."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(
            UNDOCUMENDED_STATUS.format(homework_status=homework_status))
    logger.debug(homework_status)
    return STATUS_CHANGED.format(
        homework_name=homework_name, verdict=HOMEWORK_VERDICTS[homework_status]
    )


def check_tokens():
    """Проверка наличия токенов."""
    for name in TOKENS:
        if not globals()[name]:
            logger.critical(ERROR_TOKENS.format(name=name))
            return False
    return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            current_timestamp = response.get('current_date')
            if homework:
                send_message(bot, parse_status(homework[0]))
            else:
                logger.debug(NO_NEW_CHECKS)
            time.sleep(RETRY_TIME)

        except Exception as error:
            logger.error(error)
            send_message(bot, ERROR_PROJECT)


if __name__ == '__main__':
    main()
