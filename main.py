import datetime
import json
from datetime import datetime, timedelta, timezone

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from discord import HTTPException

import band_manager
import code_manager
import commands
import content_manager
import gear_calendar
import settings_manager

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)

token = json.loads(open("bot_token.json").read())['token']

band_msg_scheduler = AsyncIOScheduler()
qm_msg_scheduler = AsyncIOScheduler()
update_scheduler = BackgroundScheduler()


def remove_bot_mention(content):
    """Removes the bot mention from the message."""
    return content.replace(client.user.mention, '').lstrip()


@client.event
async def on_ready():
    # Start schedulers
    band_msg_scheduler.start()
    qm_msg_scheduler.start()
    update_scheduler.start()

    # Schedule future messages
    schedule_rehearsal_msgs()
    schedule_request_msg()
    schedule_change_reminder_msg()

    # Schedule calendar updates to start at midnight
    schedule_refresh_calendar(datetime.today() + timedelta(days=1))


@client.event
async def on_message(message):
    # Ignore message if it is written by the bot or does not contain a bot mention
    if message.author == client.user or message.content.find(client.user.mention) == -1:
        return

    content = remove_bot_mention(message.content)

    files = []
    reply = ''
    error = ''

    content_lower = content.lower()

    # Allow anyone to use the roll command or thank the bot
    if content_lower.startswith('roll'):
        reply = commands.roll(content)
    elif 'thank' in content_lower and not content_lower.startswith(('list', 'add', 'remove')):
        reply = content_manager.get_thank_you_reply()
    else:
        user_role_ids = [role.id for role in message.author.roles]
        if settings_manager.get_admin_role_id() not in user_role_ids and not content_lower.startswith('roll'):
            return # Not admin of bot: cannot execute commands: no response

        if content_lower.startswith('get code expiration'):
            reply = commands.get_code_expiration()
        elif content_lower.startswith('get code'):
            reply = commands.get_code()
        elif content_lower.startswith('update code'):
            reply = commands.update_code()
            schedule_change_reminder_msg()
        elif content_lower.startswith('set code expiration'):
            reply = commands.set_code_expiration(content)
            schedule_change_reminder_msg()
        elif content_lower.startswith('set code'):
            reply = commands.set_code(content)
            schedule_change_reminder_msg()
        elif content_lower.startswith('add band'):
            [reply, send_greeting] = commands.add_band(content)
            if send_greeting:
                error = await band_greeting_msg(band_manager.get_band(band_manager.get_bands()[-1]['name']))
        elif content_lower.startswith('list bands'):
            reply = commands.list_bands()
        elif content_lower.startswith('remove band'):
            reply = commands.remove_band(content)
        elif content_lower.startswith('change band name'):
            reply = commands.change_band_name(content)
        elif content_lower.startswith('next rehearsal'):
            reply = commands.next_rehearsal()
        elif content_lower.startswith('next request'):
            reply = commands.next_request()
        elif content_lower.startswith('set setting'):
            reply = commands.set_setting(content)
        elif content_lower.startswith('list settings'):
            reply = commands.list_settings()
        elif content_lower.startswith('refresh calendar'):
            refresh_calendar(False)
            reply = commands.refresh_calendar()
        elif content_lower.startswith('add greeting'):
            reply = commands.add_greeting(content)
        elif content_lower.startswith('remove greeting'):
            reply = commands.remove_greeting(content)
        elif content_lower.startswith('list greetings'):
            reply = commands.list_greetings()
        elif content_lower.startswith('add farewell'):
            reply = commands.add_farewell(content)
        elif content_lower.startswith('remove farewell'):
            reply = commands.remove_farewell(content)
        elif content_lower.startswith('list farewells'):
            reply = commands.list_farewells()
        elif content_lower.startswith('add thank you reply'):
            reply = commands.add_thank_you_reply(content)
        elif content_lower.startswith('remove thank you reply'):
            reply = commands.remove_thank_you_reply(content)
        elif content_lower.startswith('list thank you replies'):
            reply = commands.list_thank_you_replies()
        elif content_lower.startswith('export configs'):
            reply, files = commands.export_configs()
        elif content_lower.startswith('list commands') or content_lower.startswith('help'):
            reply = commands.list_commands()
        elif content_lower.startswith('quit'):
            exit(0)
        else:
            reply = commands.bad_command()

    if len(reply) != 0:
        if isinstance(reply, list):
            for r in reply:
                await message.reply(r)
        else:
            if len(reply) > 2000:
                reply = content_manager.split_content(reply)
            await message.reply(reply, files=[discord.File(path) for path in files])

    if len(error) != 0:
        await message.reply(error)


async def get_message_history(channel, start, end):
    history = []
    async for message in channel.history(after=start, before=end):
        history.append(message)
    return history


async def band_member_sent_image(band, start, stop=None):
    if stop is None:
        stop = datetime.now().replace(second=0, microsecond=0)
    channel = client.get_channel(band['channel_id'])
    history = await get_message_history(channel, start, stop)
    for message in history:
        if band['role_id'] in [role.id for role in message.author.roles] and message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    return True
    return False


async def rehearsal_code_msg(bands, time):
    """Shares the lockbox code with all given bands."""
    for band in bands:
        channel = client.get_channel(band['channel_id'])
        mention = band['role']
        code = code_manager.get_curr_code()
        msg = content_manager.format_message(content_manager.get_message('rehearsal code'), time, {'code': code}, mention, True)
        await channel.send(msg)

    schedule_rehearsal_msgs()


async def request_code_msg(requests, time):
    """Sends the lockbox code for the given requests to the Quartermaster."""
    mention = settings_manager.get_setting('quartermaster_role')
    code = code_manager.get_curr_code()
    channel = client.get_channel(settings_manager.get_quartermaster_channel_id())
    formatted_requests = []
    for request in requests:
        name = request['name']
        start = request['start'].time()
        end = request['end'].time()
        formatted_requests.append(content_manager.format_message(content_manager.get_message('request code')['for request'], time, {'name': name, 'start': start, 'end': end}))
    requests_joined = content_manager.get_message('request code')['join requests'].join(formatted_requests)
    msg = content_manager.format_message(content_manager.get_message('request code')['message'], time, {'code': code, 'requests': requests_joined}, mention, False)
    await channel.send(msg)

    schedule_request_msg(requests[-1]['end'])


async def change_reminder_msg(time):
    """Reminds the Quartermaster to change the lockbox code and what to change it to."""
    channel = client.get_channel(settings_manager.get_quartermaster_channel_id())
    mention = settings_manager.get_setting('quartermaster_role')
    msg = content_manager.format_message(content_manager.get_message('quartermaster change reminder'), time, {'code': code_manager.get_next_code()}, mention, False)
    await channel.send(msg)


async def change_re_reminder_msg(time):
    """Re-reminds the Quartermaster to change the lockbox code and what to change it to."""
    channel = client.get_channel(settings_manager.get_quartermaster_channel_id())
    mention = settings_manager.get_setting('quartermaster_role')
    msg = content_manager.format_message(content_manager.get_message('quartermaster change re-reminder'), time, {'code': code_manager.get_next_code()}, mention, False)
    await channel.send(msg)


async def picture_before_reminder_msg(rehearsal_start, bands):
    mode = settings_manager.get_setting('picture_before_reminder_mode')
    if mode == 0:
        return # Reminder disabled
    elif mode == 1:
        start = rehearsal_start - timedelta(minutes=settings_manager.get_setting('setup_time_mins') + settings_manager.get_setting('teardown_time_mins'))
        if len(gear_calendar.get_requests_in_range(start, rehearsal_start, include_start=True)) > 0:
            return # Adjacent or overlapping rehearsal

    start = rehearsal_start - timedelta(minutes=settings_manager.get_setting('setup_time_mins'))
    end = rehearsal_start + timedelta(minutes=settings_manager.get_setting('picture_before_reminder_mins'))

    for band in bands:
        # Check if band member sent image since code was given
        if await band_member_sent_image(band, start, end): # TODO check if this works
            channel = client.get_channel(band['channel_id'])
            mention = band['role']
            msg = content_manager.format_message(content_manager.get_message('picture before rehearsal reminder'), end, {}, mention, True)
            await channel.send(msg)


async def picture_after_reminder_msg(rehearsal_start, rehearsal_end, band):
    mode = settings_manager.get_setting('picture_after_reminder_mode')
    if mode == 0:
        return # Reminder disabled
    elif mode == 1:
        end = rehearsal_end + timedelta(minutes=settings_manager.get_setting('teardown_time_mins') + settings_manager.get_setting('setup_time_mins'))
        if len(gear_calendar.get_requests_in_range(rehearsal_end, end, include_end=True)) > 0:
            return # Adjacent or overlapping rehearsal

    start = rehearsal_start + ((rehearsal_end - rehearsal_start) / 2) # Halfway through rehearsal
    end = rehearsal_end + timedelta(minutes=settings_manager.get_setting('teardown_time_mins'))

    if await band_member_sent_image(band, start, end): # TODO check if this works
        channel = client.get_channel(band['channel_id'])
        mention = band['role']
        msg = content_manager.format_message(content_manager.get_message('picture after rehearsal reminder'), end, {}, mention, False)
        await channel.send(msg)


async def refresh_calendar(is_automatic=True):
    """Reschedules the lockbox code messages for bands' rehearsals in case new events have been added in the meantime."""
    # Cancel previously scheduled rehearsal messages
    band_msg_scheduler.remove_all_jobs()
    # Reschedules rehearsal message
    schedule_rehearsal_msgs()
    schedule_request_msg()
    schedule_change_reminder_msg()

    if is_automatic:
        schedule_refresh_calendar()

        if settings_manager.get_setting('notify_auto_refresh') != 0: # TODO test this feature
            # Send automatic refresh notification to quartermaster channel
            channel = client.get_channel(settings_manager.get_quartermaster_channel_id())
            mention = settings_manager.get_setting('quartermaster_role')
            msg = content_manager.format_message(content_manager.get_message('automatic refresh'), datetime.now(), {}, mention, False)
            await channel.send(msg)

    print(f'Calendar refresh took place at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}')

def schedule_rehearsal_msgs(after=None):
    """Schedules message to share the lockbox code with bands before their rehearsal."""

    # Ensure that scheduled message will be sent in the future
    if after is None:
        after = datetime.now() + timedelta(minutes=settings_manager.get_setting('setup_time_mins'))
    next_rehearsals = gear_calendar.get_next_rehearsal(after=after)

    if len(next_rehearsals) == 0:
        return # No upcoming rehearsals for now

    # Array of bands to account for edge case where two bands start rehearsal at the same time
    bands = []
    for rehearsal in next_rehearsals:
        bands.append(band_manager.get_band(rehearsal['band']))

    # Schedule message(s)
    rehearsal_start = next_rehearsals[0]['start']
    send_code_dt = rehearsal_start - timedelta(minutes=settings_manager.get_setting('setup_time_mins'))
    remind_picture_before_dt = rehearsal_start + timedelta(minutes=settings_manager.get_setting('picture_before_reminder_mins'))

    band_msg_scheduler.add_job(rehearsal_code_msg, 'date', run_date=send_code_dt, args=[bands, send_code_dt.time()], id='code msg', replace_existing=False)
    band_msg_scheduler.add_job(picture_before_reminder_msg, 'date', run_date=remind_picture_before_dt, args=[rehearsal_start, bands], id='picture before msg', replace_existing=False)

    for i in range(len(bands)):
        rehearsal_end = next_rehearsals[i]['end']
        remind_picture_after_dt = rehearsal_end + timedelta(minutes=settings_manager.get_setting('teardown_time_mins'))
        band_msg_scheduler.add_job(picture_after_reminder_msg, 'date', run_date=remind_picture_after_dt, args=[rehearsal_start, rehearsal_end, bands[i]], id='picture after msg', replace_existing=False)


def schedule_request_msg(after=None):
    """Schedules the message to remind the Quartermaster to share the lockbox code for the next request(s)."""

    # Ensure that scheduled message will be sent in the future
    if after is None:
        after = datetime.now() + timedelta(minutes=settings_manager.get_setting('setup_time_mins') + settings_manager.get_setting('quartermaster_reminder_time_mins'))
    requests = gear_calendar.get_next_request(after)

    if len(requests) == 0:
        return  # No upcoming rehearsals for now

    start = requests[0]['start']
    end = start + timedelta(minutes=settings_manager.get_setting('quartermaster_request_range_mins'))
    requests = gear_calendar.get_requests_in_range(start, end, True, True)

    # Schedule message
    send_dt = start - timedelta(minutes=settings_manager.get_setting('setup_time_mins') + settings_manager.get_setting('quartermaster_reminder_time_mins'))
    band_msg_scheduler.add_job(request_code_msg, 'date', run_date=send_dt,
                               args=[requests, send_dt.time()], id='picture before msg', replace_existing=True)


def schedule_change_reminder_msg():
    """Schedules message to the Quartermaster to change the lockbox code and what to change it to."""
    send_dt = datetime.combine(code_manager.get_expires(), settings_manager.get_change_code_reminder_time())
    if send_dt > datetime.now(tz=timezone.utc):
        qm_msg_scheduler.add_job(change_reminder_msg, 'date', run_date=send_dt, args=[send_dt.time()], id='change reminder', replace_existing=True)
    schedule_change_re_reminder_msg()


def schedule_change_re_reminder_msg():
    """Schedules message to the Quartermaster to re-remind quartermaster to change lockbox code and what to change it to."""
    delay_hours = settings_manager.get_setting('change_code_re-reminder_hours')
    if delay_hours == 0:
        return # Re-reminder disabled
    send_dt = datetime.combine(code_manager.get_expires(), settings_manager.get_change_code_reminder_time()) + timedelta(hours=delay_hours)
    if send_dt > datetime.now(tz=timezone.utc):
        qm_msg_scheduler.add_job(change_re_reminder_msg, 'date', run_date=send_dt, args=[send_dt.time()], id='change re-reminder', replace_existing=True)


def schedule_refresh_calendar(update_dt=None):
    """Schedules the update of scheduled messages."""
    if update_dt is None:
        update_dt = datetime.now(tz=timezone.utc) + timedelta(minutes=settings_manager.get_setting('calendar_refresh_mins'))
        # Truncate time to minutes to prevent drift
        update_dt = update_dt.replace(second=0, microsecond=0)

    update_scheduler.add_job(refresh_calendar, 'date', run_date=update_dt, args=[], id='calendar update')


async def band_greeting_msg(band):
    channel = client.get_channel(band['channel_id'])
    msg = content_manager.format_message(content_manager.get_message('band greeting'), datetime.now(), {'band': band['name'], 'name': client.user.display_name, 'url': settings_manager.get_setting('gear_calendar_url')}, band['role'])

    try:
        await channel.send(msg)
        return None
    except discord.errors.Forbidden:
        return f"No access to band's channel"


client.run(token)