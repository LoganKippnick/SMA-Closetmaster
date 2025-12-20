import copy

import json

json_filename = 'bands.json'

content_data = json.load(open(json_filename, 'r'))['bands']


def read_json():
    global content_data
    bands_data = json.load(open(json_filename, 'r'))['bands']


def write_json():
    json.dump({'bands': content_data}, open(json_filename, 'w'), indent=2)


def get_band(name):
    for band in content_data:
        if band['name'] == name:
            band_copy = copy.deepcopy(band)
            band_copy.update({'channel_id': int(band['channel'].removeprefix('<#').removesuffix('>')), 'role_id': int(band['role'].removeprefix('<@').removeprefix('&').removesuffix('>'))})
            return band_copy

    return None


def get_bands():
    return content_data


def add_band(name, role, channel):
    if get_band(name) is None:
        if not role.startswith('<@') or not role.endswith('>') or not role.removeprefix('<@').removeprefix('&').removesuffix('>').isdigit():
            raise ValueError('Invalid role format.')
        elif not channel.startswith('<#') or not channel.endswith('>') or not channel.removeprefix('<#').removesuffix('>').isdigit():
            raise ValueError('Invalid channel format.')
        content_data.append({'name': name, 'role': role, 'channel': channel})
        write_json()
        return
    raise ValueError(f'Band with name "{name}" already exists.')


def remove_band(name):
    for band in content_data:
        if band['name'] == name:
            content_data.remove(band)
            write_json()
            return
    raise ValueError(f'Could not find band with name "{name}".')


def change_name(old_name, new_name):
    if get_band(new_name) is not None:
        raise ValueError(f'Band with name "{new_name}" already exists.')

    for band in content_data:
        if band['name'] == old_name:
            band['name'] = new_name
            write_json()
            return
    raise ValueError(f'Could not find band with name "{old_name}".')
