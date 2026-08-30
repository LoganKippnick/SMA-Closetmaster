import json
import random

import band_manager
import code_manager
import gear_calendar
import content_manager
import settings_manager


commands_data = json.load(open('commands.json', 'r'))


def parse_args(cmd_name, content, expected_num_args=None, max_num_args=None, min_num_args=None):
    content = content.removeprefix(cmd_name).strip()
    if content.count('`') % 2 == 1:
        raise ValueError('Syntax error')
    else:
        content = content.replace('`', '')
    content = content.replace('“', '"').replace('”', '"').replace('’', '\'')
    args = []
    quotes_open = False
    brackets_open = False
    arg_open = False
    esc_open = False
    for char in list(content):
        if char == '"' and not esc_open:
            quotes_open = not quotes_open
            arg_open = not arg_open
            if arg_open:
                args.append('')
        elif char == '<' and not brackets_open and not esc_open:
            brackets_open = True
            arg_open = True
            args.append('<')
        elif char == '>' and brackets_open and not esc_open:
            args[-1] += '>'
            brackets_open = False
            arg_open = False
        elif char.isspace() and not quotes_open:
            arg_open = False
        else:
            if not arg_open:
                arg_open = True
                args.append('')

            if char == '\\' and not esc_open:
                esc_open = True
            else:
                args[-1] += char
                esc_open = False
    if quotes_open or esc_open or brackets_open:
        raise ValueError('Syntax error')
    elif expected_num_args and len(args) != expected_num_args:
        expected_plural = expected_num_args != 1
        raise ValueError(f'Expected {expected_num_args} {'arguments' if expected_plural else 'argument'}, got {len(args)} instead.')
    elif max_num_args and len(args) > max_num_args:
        minimum_plural = expected_num_args != 1
        raise ValueError(f'Maximum {max_num_args} {'arguments' if minimum_plural else 'argument'}, got {len(args)}.')
    elif min_num_args and len(args) < min_num_args:
        maximum_plural = expected_num_args != 1
        raise ValueError(f'Minimum {max_num_args} {'arguments' if maximum_plural else 'argument'}, got {len(args)}.')
    return args


def throw_error(cmd_name, error):
    params = ''
    if 'params' in commands_data[cmd_name].keys():
        params = commands_data[cmd_name]['params']
    return content_manager.format_command(content_manager.get_command('error'), {'error': error.args[0], 'name': cmd_name, 'params': params})


def next_rehearsal():
    cmd_name = 'next rehearsal'
    next_rehearsals = gear_calendar.get_next_rehearsal()

    if len(next_rehearsals) == 0:
        return content_manager.get_command(cmd_name)['no rehearsals']

    rehearsals = []
    for rehearsal in gear_calendar.get_next_rehearsal():
        rehearsals.append(
            content_manager.format_command(
                content_manager.get_command(cmd_name)['for rehearsal'],
                {
                    'band': rehearsal['band'],
                    'date': rehearsal['start'].date(),
                    'start': rehearsal['start'].time(),
                    'end': rehearsal['end'].time()}))
    return content_manager.get_command(cmd_name)['join rehearsals'].join(rehearsals)


def next_request():
    cmd_name = 'next request'
    next_requests = gear_calendar.get_next_request()

    if len(next_requests) == 0:
        return content_manager.get_command(cmd_name)['no requests']

    requests = []
    for request in gear_calendar.get_next_request():
        requests.append(
            content_manager.format_command(
                content_manager.get_command(cmd_name)['for request'],
                {
                    'name': request['name'],
                    'date': request['start'].date(),
                    'start': request['start'].time(),
                    'end': request['end'].time()}))
    return content_manager.get_command(cmd_name)['join requests'].join(requests)


def get_code():
    return content_manager.format_command(content_manager.get_command('get code'), {'code': code_manager.get_curr_code()})


def get_code_expiration():
    return content_manager.format_command(content_manager.get_command('get code expiration'), {'expiration': code_manager.get_expires()})


def update_code():
    code_manager.apply_next_code()
    return content_manager.format_command(content_manager.get_command('update code'), {'code': code_manager.get_curr_code(), 'expiration': code_manager.get_expires()})


def set_code(message):
    cmd_name = 'set code'
    try:
        code = parse_args(cmd_name, message, expected_num_args=1)[0]
        code_manager.set_code(code)
        return content_manager.format_command(content_manager.get_command('set code'), {'code': code_manager.get_curr_code(), 'expiration': code_manager.get_expires()})
    except ValueError as e:
        return throw_error(cmd_name, e)


def set_code_expiration(message):
    cmd_name = 'set code expiration'
    try:
        set_expires = parse_args(cmd_name, message, expected_num_args=1)[0]
        code_manager.set_expires(set_expires)
        return content_manager.format_command(content_manager.get_command('set code expiration'), {'expiration': code_manager.get_expires()})
    except ValueError as e:
        return throw_error(cmd_name, e)


def add_band(message):
    cmd_name = 'add band'
    try:
        args = parse_args(cmd_name, message, max_num_args=4, min_num_args=3)
        name = args[0]
        role = args[1]
        channel = args[2]
        send_greeting = True
        if len(args) == 4 and args[3].lower() != 'true':
            send_greeting = False
        band_manager.add_band(name, role, channel)
        return [content_manager.format_command(content_manager.get_command('add band'), {'name': name}), send_greeting]
    except ValueError as e:
        return [throw_error(cmd_name, e), False]


def list_bands():
    cmd_name = 'list bands'
    bands = band_manager.get_bands()

    if len(bands) == 0:
        return content_manager.get_command(cmd_name)['no bands']
    
    def sort_key(band):
        name = band['name'].lower()
        for article in ['the ', 'a ', 'an ']:
            if name.startswith(article):
                return name[len(article):]
        return name
    
    bands_data = []
    for band in sorted(bands, key=sort_key):
        bands_data.append(content_manager.format_command(content_manager.get_command(cmd_name)['for band'], {'name': band['name']}))

    return content_manager.get_command(cmd_name)['join bands'].join(bands_data)


def change_band_name(message):
    cmd_name = 'change band name'
    try:
        [old_name, new_name] = parse_args(cmd_name, message, expected_num_args=2)
        band_manager.change_name(old_name, new_name)
        return content_manager.format_command(content_manager.get_command('change band name'), {'old name': old_name, 'new name': new_name})
    except ValueError as e:
        return throw_error(cmd_name, e)


def remove_band(message):
    cmd_name = 'remove band'
    try:
        band_name = parse_args(cmd_name, message, expected_num_args=1)[0]
        band_manager.remove_band(band_name)
        return content_manager.format_command(content_manager.get_command(cmd_name), {'name': band_name})
    except ValueError as e:
        return throw_error(cmd_name, e)


def set_setting(message):
    cmd_name = 'set setting'
    set_value = None
    setting_name = ''

    try:
        [setting_name, setting_value] = parse_args(cmd_name, message, expected_num_args=2)
        settings_manager.set_setting(setting_name, setting_value)
        formatted_value = settings_manager.format_value(settings_manager.get_settings()[setting_name])
        return content_manager.format_command(content_manager.get_command(cmd_name), {'name': setting_name, 'formatted value': formatted_value})
    except ValueError as e:
        return throw_error(cmd_name, e)


def list_settings():
    cmd_name = 'list settings'
    settings_data = settings_manager.get_settings()
    content_data = content_manager.get_command(cmd_name)
    settings_msgs = []
    settings = []
    len_msg = 0
    for setting in settings_data.keys():
        setting_data = settings_manager.get_settings()[setting]
        formatted_value = settings_manager.format_value(setting_data)
        setting_content = content_manager.format_command(
                content_data['for setting'],
                {
                    'name': setting,
                    'formatted value': formatted_value,
                    'type': setting_data['type'],
                    'description': setting_data['description']})
        if len_msg + len(setting_content) + (len(content_manager.get_command(cmd_name)['join settings']) * len(settings)) < 2000:
            settings.append(setting_content)
            len_msg += len(setting_content)
        else:
            settings_msgs.append(content_manager.get_command(cmd_name)['join settings'].join(settings))
            settings = [setting_content]
            len_msg = len(setting_content)
    settings_msgs.append(content_manager.get_command(cmd_name)['join settings'].join(settings))
    return settings_msgs


def refresh_calendar():
    return content_manager.get_command('refresh calendar')


def add_greeting(message):
    cmd_name = 'add greeting'
    try:
        args = parse_args(cmd_name, message, max_num_args=2, min_num_args=1)
        greeting = args[0]
        category = args[1].lower() if len(args) == 2 else 'general'
        content_manager.add_greeting(greeting, category)
        return content_manager.format_command(content_manager.get_command(cmd_name), {'greeting': greeting, 'category': category})
    except ValueError as e:
        return throw_error(cmd_name, e)


def remove_greeting(message):
    cmd_name = 'remove greeting'
    try:
        args = parse_args(cmd_name, message, expected_num_args=1)
        greeting = args[0]
        content_manager.remove_greeting(greeting)
        return content_manager.format_command(content_manager.get_command(cmd_name), {'greeting': greeting})
    except ValueError as e:
        return throw_error(cmd_name, e)


def list_greetings():
    cmd_name = 'list greetings'
    greetings_data = content_manager.get_greetings()
    content_data = content_manager.get_command(cmd_name)
    categories = []
    for category in greetings_data.keys():
        greetings = []
        for greeting in greetings_data[category]:
            greetings.append(content_manager.format_command(content_data['for greeting'], {'greeting': greeting}))
        joined_greetings = content_data['join greetings'].join(greetings)
        categories.append(content_manager.format_command(content_data['for category'], {'category': category.capitalize(), 'greetings': joined_greetings}))
    return content_manager.get_command(cmd_name)['join categories'].join(categories)


def add_farewell(message):
    cmd_name = 'add farewell'
    try:
        args = parse_args(cmd_name, message, max_num_args=2, min_num_args=1)
        farewell = args[0]
        category = args[1].lower() if len(args) == 2 else 'general'
        content_manager.add_farewell(farewell, category)
        return content_manager.format_command(content_manager.get_command(cmd_name), {'farewell': farewell, 'category': category})
    except ValueError as e:
        return throw_error(cmd_name, e)


def remove_farewell(message):
    cmd_name = 'remove farewell'
    try:
        args = parse_args(cmd_name, message, expected_num_args=1)
        farewell = args[0]
        content_manager.remove_farewell(farewell)
        return content_manager.format_command(content_manager.get_command(cmd_name), {'farewell': farewell})
    except ValueError as e:
        return throw_error(cmd_name, e)


def list_farewells():
    cmd_name = 'list farewells'
    farewells_data = content_manager.get_farewells()
    content_data = content_manager.get_command(cmd_name)
    categories = []
    for category in farewells_data.keys():
        farewells = []
        for farewell in farewells_data[category]:
            farewells.append(content_manager.format_command(content_data['for farewell'], {'farewell': farewell}))
        joined_farewells = content_data['join farewells'].join(farewells)
        categories.append(content_manager.format_command(content_data['for category'], {'category': category.capitalize(), 'farewells': joined_farewells}))
    return content_manager.get_command(cmd_name)['join categories'].join(categories)


def add_thank_you_reply(message):
    cmd_name = 'add thank you reply'
    try:
        args = parse_args(cmd_name, message, expected_num_args=1)
        reply = args[0]
        content_manager.add_thank_you_reply(reply)
        return content_manager.format_command(content_manager.get_command(cmd_name), {'reply': reply})
    except ValueError as e:
        return throw_error(cmd_name, e)

def remove_thank_you_reply(message):
    cmd_name = 'remove thank you reply'
    try:
        args = parse_args(cmd_name, message, expected_num_args=1)
        reply = args[0]
        content_manager.remove_thank_you_reply(reply)
        return content_manager.format_command(content_manager.get_command(cmd_name), {'reply': reply})
    except ValueError as e:
        return throw_error(cmd_name, e)


def list_thank_you_replies():
    cmd_name = 'list thank you replies'
    replies_data = content_manager.get_thank_you_replies()
    content_data = content_manager.get_command(cmd_name)
    replies = []
    for reply in replies_data:
        replies.append(content_manager.format_command(content_data['for reply'], {'reply': reply}))
    return content_manager.get_command(cmd_name)['join replies'].join(replies)


def export_configs():
    cmd_name = 'export configs'
    jsons = ['bands.json', 'commands.json', 'content.json', 'lockbox_code.json', 'settings.json']
    return content_manager.get_command(cmd_name), jsons


def list_commands():
    cmd_name = 'list commands'
    commands_msgs = []
    commands = []
    len_msg = 0
    for command in commands_data.keys():
        command_data = commands_data[command]
        params = ''
        if 'params' in command_data.keys():
            params = command_data['params']
        command_content = content_manager.format_command(content_manager.get_command(cmd_name)['for command'], {'name': command, 'params': params, 'description': command_data['description']})
        if len_msg + len(command_content) + (len(content_manager.get_command(cmd_name)['join commands']) * len(commands)) < 2000:
            commands.append(command_content)
            len_msg += len(command_content)
        else:
            commands_msgs.append(content_manager.get_command(cmd_name)['join commands'].join(commands))
            commands = [command_content]
            len_msg = len(command_content)
    commands_msgs.append(content_manager.get_command(cmd_name)['join commands'].join(commands))
    return commands_msgs


def bad_command():
    return content_manager.get_command('bad command')


def roll(message):
    cmd_name = 'roll'
    try:
        args = parse_args(cmd_name, message, min_num_args=0, max_num_args=2)
        size = 20
        num_dice = 1
        if len(args) >= 1:
            if args[0].isdigit() and int(args[0]) != 0:
                size = int(args[0])
            else:
                raise ValueError('Invalid die size.')
        if len(args) == 2:
            if args[1].isdigit() and int(args[1]) != 0:
                num_dice = int(args[1])
            else:
                raise ValueError('Invalid number of dice.')

        formatted_type = f'd{size}'
        if num_dice > 1:
            formatted_type += 's'

        rolls = [content_manager.format_command(content_manager.get_command(cmd_name)['start'], {'num': num_dice, 'formatted type': formatted_type})]
        for i in range(num_dice):
            dice_roll = random.randint(1, size)
            article = 'a'
            if dice_roll == 11 or dice_roll == 18 or str(dice_roll).startswith('8'):
                article = 'an'
            msg = ''
            if dice_roll == 1:
                msg = content_manager.format_command(content_manager.get_command(cmd_name)['min'], {'article': article, 'roll': dice_roll})
            elif dice_roll == size:
                msg = content_manager.format_command(content_manager.get_command(cmd_name)['max'], {'article': article, 'roll': dice_roll})
            else:
                msg = content_manager.format_command(content_manager.get_command(cmd_name)['default'], {'article': article, 'roll': dice_roll})

            rolls.append(msg)

        return content_manager.get_command(cmd_name)['join rolls'].join(rolls)
    except ValueError as e:
        return throw_error(cmd_name, e)