from datetime import date, timedelta

import json
import random

from dateutil import parser
from dateutil.parser import ParserError

import settings_manager

json_filename = 'lockbox_code.json'

json_data = json.load(open(json_filename, 'r'))


def read_json():
    global json_data
    json_data = json.load(open(json_filename, 'r'))


def write_json():
    json.dump(json_data, open(json_filename, 'w'), indent=2)


def get_curr_code():
    return json_data['curr_code']


def get_next_code():
    return json_data['next_code']


def get_expires():
    return date.fromisoformat(json_data['expires'])


def generate_expires_date():
    weekend_mode = settings_manager.get_setting('weekend_change_code_reminder_mode')
    min_days = settings_manager.get_setting('min_change_code_days')

    if weekend_mode <= 1:
        days_until_monday = date.today().weekday() % 7
        if days_until_monday == 0:
            days_until_monday = 7

        num_days = 6 if weekend_mode == 1 else 5

        if min_days >= num_days:
            min_days = 0

        expire_delta = timedelta(days=days_until_monday + random.randint(min_days, num_days))
    else:
        days_until_sunday = (date.today().weekday() % 7) - 1
        if days_until_sunday <= 0:
            days_until_sunday += 7

        num_days = 6 if weekend_mode == 2 else 7

        if min_days >= num_days:
            min_days = 0

        expire_delta = timedelta(days=days_until_sunday + random.randint(min_days, num_days))

    return date.today() + expire_delta


def generate_next_code():
    """Generates a random next code and sets a weekday next week it should be applied"""
    code = ''
    for i in range(0, 4):
        code += str(random.randint(0, 9))

    expires_date = generate_expires_date()

    json_data['next_code'] = code
    json_data['expires'] = expires_date.isoformat()

    write_json()

    return code


def apply_next_code():
    """Sets the next code to the current code and generates a new next code"""
    json_data['curr_code'] = json_data['next_code']
    write_json()

    generate_next_code()


def set_code(code):
    if code.isdigit() and len(code) == 4:
        json_data['curr_code'] = code
        json_data['expires'] = generate_expires_date().isoformat()
        write_json()
    else:
        raise ValueError(f'Invalid code: "{code}"')


def set_expires(expires_str):
    try:
        expires_date = parser.parse(expires_str).date()
    except ParserError:
        raise ValueError('Invalid date.')

    if expires_date < date.today():
        raise ValueError('Date cannot be in the past.')

    json_data['expires'] = expires_date.isoformat()
    write_json()