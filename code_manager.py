from datetime import date, datetime, timedelta

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


def _is_expiration_day_allowed(expiration_date, weekend_mode):
    weekday = expiration_date.weekday()
    if weekend_mode == 0:
        return weekday < 5
    if weekend_mode == 1:
        return weekday < 6
    if weekend_mode == 2:
        return weekday != 5
    return True


def _next_allowed_expiration_date(expiration_date, weekend_mode):
    while not _is_expiration_day_allowed(expiration_date, weekend_mode):
        expiration_date += timedelta(days=1)
    return expiration_date


def normalize_expiration_date(expiration_date):
    weekend_mode = settings_manager.get_setting('weekend_change_code_reminder_mode')
    return _next_allowed_expiration_date(expiration_date, weekend_mode)


def normalize_stored_expiration_date():
    expires = get_expires()
    normalized_expires = normalize_expiration_date(expires)
    if normalized_expires != expires:
        json_data['expires'] = normalized_expires.isoformat()
        write_json()
    return normalized_expires


def generate_expires_date():
    weekend_mode = settings_manager.get_setting('weekend_change_code_reminder_mode')
    min_days = settings_manager.get_setting('min_change_code_days')
    today = datetime.now(tz=settings_manager.get_timezone()).date()
    earliest_date = today + timedelta(days=min_days)
    candidate_dates = []
    for days_after_minimum in range(7):
        candidate = earliest_date + timedelta(days=days_after_minimum)
        if _is_expiration_day_allowed(candidate, weekend_mode):
            candidate_dates.append(candidate)
    return random.choice(candidate_dates)


def generate_next_code():
    """Generates a random next code and an expiration date respecting configured scheduling rules."""
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

    today = datetime.now(tz=settings_manager.get_timezone()).date()
    if expires_date < today:
        raise ValueError('Date cannot be in the past.')

    expires_date = normalize_expiration_date(expires_date)
    json_data['expires'] = expires_date.isoformat()
    write_json()