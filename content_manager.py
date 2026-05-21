import copy
import json
import random
import re

json_filename = 'content.json'

content_data = json.load(open(json_filename, 'r'))


def read_json():
    global content_data
    content_data = json.load(open(json_filename, 'r'))


def write_json():
    json.dump(content_data, open(json_filename, 'w'), indent=2)


def get_greetings():
    return copy.deepcopy(content_data['greetings'])


def get_greeting(msg_time=None):
    greetings = get_greetings()['general']
    if msg_time is not None:
        if 4 <= msg_time.hour <= 10:
            greetings.extend(get_greetings()['morning'])
        elif 11 <= msg_time.hour <= 12:
            greetings.extend(get_greetings()['day'])
        elif 13 <= msg_time.hour <= 17:
            greetings.extend(get_greetings()['afternoon'])
        elif 18 <= msg_time.hour <= 22:
            greetings.extend(get_greetings()['evening'])

    return greetings[random.randint(0, len(greetings) - 1)]


def get_farewells():
    return copy.deepcopy(content_data['farewells'])


def get_farewell(msg_time=None, is_rehearsal=False):
    farewells = get_farewells()['general']
    if msg_time is not None:
        if msg_time.hour < 9:
            farewells.extend(get_farewells()['day'])
        elif not is_rehearsal:
            farewells.extend(get_farewells()['night'])

    if is_rehearsal:
        farewells.extend(get_farewells()['rehearsal'])

    return farewells[random.randint(0, len(farewells) - 1)]


def get_thank_you_replies():
    return copy.deepcopy(content_data['thank you replies'])


def get_thank_you_reply():
    thank_you_replies = get_thank_you_replies()
    return thank_you_replies[random.randint(0, len(thank_you_replies) - 1)]


def get_command(cmd_name):
    return content_data['commands'][cmd_name]


def get_message(msg_name):
    return content_data['messages'][msg_name]


def add_greeting(greeting, category=None):
    if category is None:
        category = 'general'

    if category not in content_data['greetings'].keys():
        raise ValueError(f'Invalid category: "{category}" not one of [{', '.join([f'`{key}`' for key in content_data['greetings'].keys()])}]')
    else:
        for existing_greeting in content_data['greetings'][category]:
            if existing_greeting == greeting:
                raise ValueError(f'Duplicate greeting "{existing_greeting}" in category "{category}".')
        content_data['greetings'][category].append(greeting)

    write_json()


def add_farewell(farewell, category=None):
    if category is None:
        category = 'general'

    if category not in content_data['farewells'].keys():
        raise ValueError(
            f'Invalid section: "{category}" not one of [{', '.join([f'`{key}`' for key in content_data['farewells'].keys()])}]')
    else:
        for existing_farewell in content_data['farewells'][category]:
            if existing_farewell == farewell:
                raise ValueError(f'Duplicate farewell "{existing_farewell}" in category "{category}".')
        content_data['farewells'][category].append(farewell)

    write_json()


def add_thank_you_reply(reply):
    for existing_reply in content_data['thank you replies']:
        if existing_reply == reply:
            raise ValueError(f'Duplicate thank you reply "{existing_reply}".')
    content_data['thank you replies'].append(reply)

    write_json()


def remove_greeting(greeting):
    greeting_removed = False
    for category in content_data['greetings'].keys():
        while greeting in content_data['greetings'][category]:
            content_data['greetings'][category].remove(greeting)
            write_json()
            greeting_removed = True
    if not greeting_removed:
        raise ValueError(f'Greeting "{greeting}" not found.')


def remove_farewell(farewell):
    farewell_removed = False
    for category in content_data['farewells'].keys():
        if farewell in content_data['farewells'][category]:
            content_data['farewells'][category].remove(farewell)
            write_json()
            farewell_removed = True
    if not farewell_removed:
        raise ValueError(f'Farewell "{farewell}" not found.')


def remove_thank_you_reply(reply):
    if reply in content_data['thank you replies']:
        content_data['thank you replies'].remove(reply)
        write_json()
    else:
        raise ValueError(f'Thank you reply "{reply}" not found.')


def format_command(cmd, data):
    return cmd.format(**data)


def format_message(msg, msg_time, data, mention=None, is_rehearsal=False):
    msg = msg.replace('{greeting}', get_greeting(msg_time))
    msg = msg.replace('{farewell}', get_farewell(msg_time, is_rehearsal))
    if mention is not None:
        msg = msg.replace('{mention}', mention)
    return msg.format(**data)


def split_content(content):
    contents = []
    while len(content) > 2000:
        search_substr = content[:2000]
        split_len = search_substr.rfind('\n')
        if split_len <= 0:
            ws_list = list(re.finditer(r'\s', search_substr))
            if len(ws_list) > 0:
                split_len = ws_list[-1].span()[0]
            if split_len <= 0:
                split_len = 2000
        contents.append(content[:split_len].strip())
        content = content[split_len:].strip()

    return contents