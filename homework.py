import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

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

SEND_MESSAGE = 'Отправка сообщения: {message}'
ERROR_SEND_MESSAGE = ('Не удалось отправить сообщение {message},'
                      'ошибка: {error}')
ERROR_CONNECTING = 'Ошибка соединения: {error}'
RESPONSE_UNEXPECTED = ('Неожиданный ответ сервера, ошибка: {error}'
                       'Ответ API: {status_code}')
ERROR_REPONSE = 'Неожиданный ответ сервера. Ответ API: {status_code}'
ERROR_KEY = 'Данных ключей в запросе API не найдено'
RESPONSE_TYPE = 'Неожиданный формат данных: ошибка {type}'
HOMEWORK_TYPE = 'Неожиданный формат данных домашнего задания: {type}'
ERROR_MESSAGE_STATUS = ('Статус {homework_status} '
                        'домашней работы: {homework_name} не документирован.')
STATUS_CHANGED = 'Изменился статус проверки работы "{homework_name}".{verdict}'
ERROR_PROJECT = 'Сбой в работе программы: {error}'
ERROR_TOKENS = 'Отсутствуют обязательные токены: {name}'
ERROR_SEND_ERROR = 'Не удалось отправить сообщение об ошибке: {error}'
NO_NEW_CHECKS = 'Нет новых работ для проверки статуса'
ERROR_BOT = 'Работа бота остановлена'
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
        logger.exception(ERROR_SEND_MESSAGE.format(
            message=message,
            error=error))
        raise error


def get_api_answer(timestamp):
    """Запрос к API."""
    request = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': timestamp}
    )
    try:
        response_statuses = requests.get(**request)
    except requests.exceptions.RequestException as connect_err:
        raise ConnectionError(ERROR_CONNECTING.format(
            **request, error=connect_err))
    statuses = response_statuses.json()
    for field in ['error', 'code']:
        if field in statuses:
            raise RuntimeError(
                RESPONSE_UNEXPECTED.format(
                    **request, error=statuses.get(field),
                    status_code=field))
    if response_statuses.status_code != HTTPStatus.OK.value:
        raise ValueError(ERROR_REPONSE.format(
            **request, status_code=response_statuses.status_code))
    return statuses


def check_response(response):
    """Проверка API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(RESPONSE_TYPE.format(type=type(response)))
    try:
        homeworks = response['homeworks']
    except KeyError as error:
        logger.error(ERROR_KEY)
        raise error
    if not isinstance(homeworks, list):
        raise TypeError(HOMEWORK_TYPE.format(type=type(homeworks)))
    return homeworks


def parse_status(homework):
    """Сообщение с информацией о ревью."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(
            ERROR_MESSAGE_STATUS.format(
                homework_status=homework_status,
                homework_name=homework_name))
    logger.debug(homework_status)
    return STATUS_CHANGED.format(
        homework_name=homework_name, verdict=HOMEWORK_VERDICTS[homework_status]
    )


def check_tokens():
    """Проверка наличия токенов."""
    empty_tokens = [name for name in TOKENS if not globals()[name]]
    if empty_tokens:
        logger.critical(ERROR_TOKENS.format(
            name=empty_tokens))
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError(ERROR_BOT)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    error_message = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            current_timestamp = response.get('current_date', current_timestamp)
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))

        except Exception as error:
            message = ERROR_PROJECT.format(error=error)
            logger.error(message)
            if error_message != message:
                try:
                    send_message(bot, message)
                except Exception as error:
                    logger.exception(ERROR_SEND_ERROR.format(error=error))
                else:
                    error_message = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
