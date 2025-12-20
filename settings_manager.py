import json
from datetime import time, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil import parser

json_filename = 'settings.json'

settings = json.load(open(json_filename, 'r'))

def read_json():
    global settings
    settings = json.load(open(json_filename, 'r'))


def write_json():
    json.dump(settings, open(json_filename, 'w'), indent=2)


def get_setting(key):
    if key in settings:
        return settings[key]['value']
    else:
        raise ValueError(f'No such setting: `{key}`.')


def get_settings():
    return settings


def set_setting(key, value):
    if key in settings.keys():
        setting_type = settings[key]['type']
        if setting_type == 'uint':
            if value.isdigit():
                settings[key]['value'] = int(value)
                write_json()
                return
        elif setting_type == 'time':
            try:
                iso_time = parser.parse(value).time().isoformat()
                settings[key]['value'] = iso_time
                write_json()
                return
            except ValueError:
                pass
        elif setting_type == 'tz str':
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError:
                raise ValueError(f'Invalid timezone: `"{value}"`.')
        else:
            settings[key]['value'] = value
            write_json()
            return
        raise ValueError(f'Value for setting `{key}` is not of type `{setting_type}`.')
    raise ValueError(f'No such setting: `{key}`.')


def format_value(setting):
    formatted = str(setting['value'])
    if setting['type'] in ['str', 'tz str']:
        formatted = f'"{formatted}"'
    if setting['type'] not in ['@role', '#channel']:
        formatted = f'`{formatted}`'
    return formatted


def get_timezone():
    return ZoneInfo(get_setting('timezone'))


def get_change_code_reminder_time():
    return time.fromisoformat(get_setting('change_code_reminder_time')).replace(tzinfo=get_timezone())


def get_quartermaster_channel_id():
    return int(get_setting('quartermaster_channel').removeprefix('<#').removesuffix('>'))


def get_admin_role_id():
    return int(get_setting('admin_role').removeprefix('<@').removeprefix('&').removesuffix('>'))