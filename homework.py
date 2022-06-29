import os
import logging
from logging.handlers import RotatingFileHandler
import requests
from http import HTTPStatus

import time
import telegram

from dotenv import load_dotenv
from exception import HTTPNot200

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='telegramm_bot.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    filemode='w'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'my_logger.log', maxBytes=50000000, backupCount=5
)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Send message')
    except Exception:
        logger.error('мимо!')
        return ('мимо!')


def get_api_answer(current_timestamp):
    """Запрос к API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        current_timestamp = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
    except requests.exceptions.HTTPError as http_err:
        logger.error("Http Error:", http_err)
        return ("Http Error:", http_err)
    except requests.exceptions.ConnectionError as connect_err:
        logger.error("Error Connecting:", connect_err)
        return ("Error Connecting:", connect_err)
    if current_timestamp.status_code != HTTPStatus.OK.value:
        raise HTTPNot200('HTTPNot200')
    current_timestamp = current_timestamp.json()
    logger.debug('удачно!')
    return current_timestamp


def check_response(response):
    """Проверка API на корректность."""
    if len(response) == 0:
        logger.error('Empty response')
    try:
        homeworks = response['homeworks']
    except KeyError as errkey:
        logger.error('Key Error', errkey)
        return ('Key homeworks no in response ', errkey)
    logger.debug('answer homework done')
    return homeworks[0]


def parse_status(homework):
    """Сообщение с информацией о ревью."""
    if 'homework_name' not in homework:
        raise KeyError('Empty value homework_name')
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise KeyError('Empty value status')
    homework_status = homework['status']
    logger.debug(homework_status)
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except KeyError as errkey:
        logger.error('Undocumented status of homework.', errkey)
        return ('Undocumented status of homework.', errkey)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия токенов."""
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logger.critical(
            'Not all required environment variables have been passed'
        )
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
            message = parse_status(homework)
            send_message(bot, message)
            time.sleep(RETRY_TIME)

        except Exception as error:
            logger.error(error)
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
