import datetime
import json
from datetime import datetime, timedelta, timezone

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
author_user_id = int(json.loads(open('discord_author_creds.json').read())['author user id'])

band_msg_scheduler = AsyncIOScheduler()
qm_msg_scheduler = AsyncIOScheduler()
update_scheduler = AsyncIOScheduler()


def remove_bot_mention(content):
    """Removes the bot mention from the message."""
    return content.replace(client.user.mention, '').lstrip()


@client.event
async def on_ready():
    # Start schedulers
    if not band_msg_scheduler.running:
        band_msg_scheduler.start()
    if not qm_msg_scheduler.running:
        qm_msg_scheduler.start()
    if not update_scheduler.running:
        update_scheduler.start()

    # Schedule future messages
    schedule_rehearsal_msgs()
    schedule_request_msg()
    schedule_change_reminder_msg()

    # Schedule calendar updates to start at midnight
    schedule_refresh_calendar(datetime.today().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=settings_manager.get_timezone()) + timedelta(days=1))


@client.event
async def on_message(message):
    # Ignore message if it is written by the bot or does not contain a bot mention
    if message.author == client.user or message.content.find(client.user.mention) == -1:
        return

    content = remove_bot_mention(message.content)

    files = []
    reply = None
    error = None

    content_lower = content.lower()

    # Allow anyone to use the roll command or thank the bot
    if commands.command_starts_with(content_lower, 'roll'):
        reply = commands.roll(content)
    elif 'thank' in content_lower and not content_lower.startswith(('list', 'add', 'remove')):
        reply = content_manager.get_thank_you_reply()
    else:
        # Commands must start with bot mention and must be given by bot admins or author, otherwise no action
        user_role_ids = [role.id for role in message.author.roles]
        if (settings_manager.get_admin_role_id() not in user_role_ids and message.author.id != author_user_id) or not message.content.lstrip().startswith(client.user.mention):
            return

        if commands.command_starts_with(content_lower, 'get_code_expiration'):
            reply = commands.get_code_expiration()
        elif commands.command_starts_with(content_lower, 'get_code'):
            reply = commands.get_code()
        elif commands.command_starts_with(content_lower, 'update_code'):
            reply = commands.update_code()
            schedule_change_reminder_msg()
        elif commands.command_starts_with(content_lower, 'set_code_expiration'):
            reply = commands.set_code_expiration(content)
            schedule_change_reminder_msg()
        elif commands.command_starts_with(content_lower, 'set_code'):
            reply = commands.set_code(content)
            schedule_change_reminder_msg()
        elif commands.command_starts_with(content_lower, 'add_band'):
            [reply, send_greeting] = commands.add_band(content)
            if send_greeting:
                error = await band_greeting_msg(band_manager.get_band(band_manager.get_bands()[-1]['name']))
            await refresh_calendar()
        elif commands.command_starts_with(content_lower, 'list_bands'):
            reply = commands.list_bands()
        elif commands.command_starts_with(content_lower, 'remove_band'):
            reply = commands.remove_band(content)
            await refresh_calendar()
        elif commands.command_starts_with(content_lower, 'rename_band'):
            reply = commands.rename_band(content)
        elif commands.command_starts_with(content_lower, 'next_rehearsal'):
            reply = commands.next_rehearsal()
        elif commands.command_starts_with(content_lower, 'next_request'):
            reply = commands.next_request()
        elif commands.command_starts_with(content_lower, 'set_setting'):
            reply = commands.set_setting(content)
            schedule_change_reminder_msg()
        elif commands.command_starts_with(content_lower, 'list_settings'):
            reply = commands.list_settings()
        elif commands.command_starts_with(content_lower, 'refresh_calendar'):
            await refresh_calendar()
            reply = commands.refresh_calendar()
        elif commands.command_starts_with(content_lower, 'add_greeting'):
            reply = commands.add_greeting(content)
        elif commands.command_starts_with(content_lower, 'remove_greeting'):
            reply = commands.remove_greeting(content)
        elif commands.command_starts_with(content_lower, 'list_greetings'):
            reply = commands.list_greetings()
        elif commands.command_starts_with(content_lower, 'add_farewell'):
            reply = commands.add_farewell(content)
        elif commands.command_starts_with(content_lower, 'remove_farewell'):
            reply = commands.remove_farewell(content)
        elif commands.command_starts_with(content_lower, 'list_farewells'):
            reply = commands.list_farewells()
        elif commands.command_starts_with(content_lower, 'add_thank_you_reply'):
            reply = commands.add_thank_you_reply(content)
        elif commands.command_starts_with(content_lower, 'remove_thank_you_reply'):
            reply = commands.remove_thank_you_reply(content)
        elif commands.command_starts_with(content_lower, 'list_thank_you_replies'):
            reply = commands.list_thank_you_replies()
        elif commands.command_starts_with(content_lower, 'export_configs'):
            reply, files = commands.export_configs()
        elif commands.command_starts_with(content_lower, 'list_commands') or commands.command_starts_with(content_lower, 'help'):
            reply = commands.list_commands()
        elif commands.command_starts_with(content_lower, 'quit'):
            exit(0)
        else:
            reply = commands.bad_command()

    replies = []

    if reply is not None:
        if isinstance(reply, list):
            for r in reply:
                replies.extend(content_manager.split_content(r))
        else:
            replies.extend(content_manager.split_content(reply))

        if replies:
            # Attach files to first reply only
            await message.reply(replies[0], files=[discord.File(path) for path in files])

            for r in replies[1:]:
                await message.reply(r)

    if error is not None:
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
        if not await band_member_sent_image(band, start, end):
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

    if not await band_member_sent_image(band, start, end):
        channel = client.get_channel(band['channel_id'])
        mention = band['role']
        msg = content_manager.format_message(content_manager.get_message('picture after rehearsal reminder'), end, {}, mention, False)
        await channel.send(msg)


async def refresh_calendar(is_automatic=False):
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
    """Schedules message to share the lockbox code with bands before their rehearsal, for the next upcoming rehearsal."""

    # Ensure that scheduled message will be sent in the future
    if after is None:
        after = datetime.now() + timedelta(minutes=settings_manager.get_setting('setup_time_mins'))
    next_rehearsals = gear_calendar.get_next_rehearsal(after=after)

    # Also get current rehearsals in case a refresh happens mid-rehearsal
    current_rehearsals = gear_calendar.get_curr_rehearsal()
    print(f'[schedule_rehearsal_msgs] after={after!r}, next_rehearsals={len(next_rehearsals)}, current_rehearsals={len(current_rehearsals)}')

    if len(next_rehearsals) == 0 and len(current_rehearsals) == 0:
        print('[schedule_rehearsal_msgs] No rehearsal messages scheduled: no upcoming or current rehearsals.')
        return # No upcoming rehearsals for now

    # Handle next rehearsals
    if len(next_rehearsals) > 0:
        # Array of bands to account for edge case where two bands start rehearsal at the same time
        bands = []
        for rehearsal in next_rehearsals:
            bands.append(band_manager.get_band(rehearsal['band']))

        # Schedule message(s)
        rehearsal_start = next_rehearsals[0]['start']
        send_code_dt = rehearsal_start - timedelta(minutes=settings_manager.get_setting('setup_time_mins'))
        remind_picture_before_dt = rehearsal_start + timedelta(minutes=settings_manager.get_setting('picture_before_reminder_mins'))
        band_names = ', '.join(band['name'] for band in bands)

        code_job_id = f'code msg {band_names} {send_code_dt.strftime("%Y-%m-%d %H:%M:%S")}'
        print(f'[schedule_rehearsal_msgs] Scheduling {code_job_id}: rehearsal_start={rehearsal_start.isoformat()}, run_date={send_code_dt.isoformat()}, callback_msg_time={send_code_dt.time().isoformat()} (hour={send_code_dt.hour}), bands={[band["name"] for band in bands]}')
        band_msg_scheduler.add_job(rehearsal_code_msg, 'date', run_date=send_code_dt, args=[bands, send_code_dt.time()], id=code_job_id, replace_existing=True)

        picture_before_job_id = f'picture before msg {band_names} {remind_picture_before_dt.strftime("%Y-%m-%d %H:%M:%S")}'
        print(f'[schedule_rehearsal_msgs] Scheduling {picture_before_job_id}: run_date={remind_picture_before_dt.isoformat()}, rehearsal_start={rehearsal_start.isoformat()}, bands={[band["name"] for band in bands]}')
        band_msg_scheduler.add_job(picture_before_reminder_msg, 'date', run_date=remind_picture_before_dt, args=[rehearsal_start, bands], id=picture_before_job_id, replace_existing=True)

        for i in range(len(bands)):
            rehearsal_end = next_rehearsals[i]['end']
            remind_picture_after_dt = rehearsal_end + timedelta(minutes=settings_manager.get_setting('teardown_time_mins'))
            picture_after_job_id = f'picture after msg {bands[i]["name"]} {remind_picture_after_dt.strftime("%Y-%m-%d %H:%M:%S")}'
            print(f'[schedule_rehearsal_msgs] Scheduling {picture_after_job_id}: run_date={remind_picture_after_dt.isoformat()}, rehearsal_start={rehearsal_start.isoformat()}, rehearsal_end={rehearsal_end.isoformat()}, band={bands[i]["name"]!r}')
            band_msg_scheduler.add_job(picture_after_reminder_msg, 'date', run_date=remind_picture_after_dt, args=[rehearsal_start, rehearsal_end, bands[i]], id=picture_after_job_id, replace_existing=True)

    # Handle current rehearsals - schedule any messages that haven't been sent yet
    if len(current_rehearsals) > 0:
        now = datetime.now(tz=settings_manager.get_timezone())
        for rehearsal in current_rehearsals:
            band = band_manager.get_band(rehearsal['band'])
            rehearsal_start = rehearsal['start']
            rehearsal_end = rehearsal['end']

            # Check and schedule picture before message if it hasn't been sent yet
            remind_picture_before_dt = rehearsal_start + timedelta(minutes=settings_manager.get_setting('picture_before_reminder_mins'))
            if remind_picture_before_dt >= now:
                picture_before_job_id = f'picture before msg {band["name"]} {remind_picture_before_dt.strftime("%Y-%m-%d %H:%M:%S")}'
                print(f'[schedule_rehearsal_msgs] Scheduling {picture_before_job_id}: run_date={remind_picture_before_dt.isoformat()}, now={now.isoformat()}, rehearsal_start={rehearsal_start.isoformat()}, band={band["name"]!r}')
                band_msg_scheduler.add_job(picture_before_reminder_msg, 'date', run_date=remind_picture_before_dt, args=[rehearsal_start, [band]], id=picture_before_job_id, replace_existing=True)
            else:
                print(f'[schedule_rehearsal_msgs] Skipping picture-before reminder for {band["name"]!r}: run_date={remind_picture_before_dt.isoformat()} is before now={now.isoformat()}.')

            # Check and schedule picture after message if it hasn't been sent yet
            remind_picture_after_dt = rehearsal_end + timedelta(minutes=settings_manager.get_setting('teardown_time_mins'))
            if remind_picture_after_dt >= now:
                picture_after_job_id = f'picture after msg {band["name"]} {remind_picture_after_dt.strftime("%Y-%m-%d %H:%M:%S")}'
                print(f'[schedule_rehearsal_msgs] Scheduling {picture_after_job_id}: run_date={remind_picture_after_dt.isoformat()}, now={now.isoformat()}, rehearsal_start={rehearsal_start.isoformat()}, rehearsal_end={rehearsal_end.isoformat()}, band={band["name"]!r}')
                band_msg_scheduler.add_job(picture_after_reminder_msg, 'date', run_date=remind_picture_after_dt, args=[rehearsal_start, rehearsal_end, band], id=picture_after_job_id, replace_existing=True)
            else:
                print(f'[schedule_rehearsal_msgs] Skipping picture-after reminder for {band["name"]!r}: run_date={remind_picture_after_dt.isoformat()} is before now={now.isoformat()}.')


def schedule_request_msg(after=None):
    """Schedules the message to remind the Quartermaster to share the lockbox code for the next request(s)."""

    # Ensure that scheduled message will be sent in the future
    if after is None:
        after = datetime.now() + timedelta(minutes=settings_manager.get_setting('setup_time_mins') + settings_manager.get_setting('quartermaster_reminder_time_mins'))
    requests = gear_calendar.get_next_request(after)

    if len(requests) > 0:
        start = requests[0]['start']
        end = start + timedelta(minutes=settings_manager.get_setting('quartermaster_request_range_mins'))
        requests = gear_calendar.get_requests_in_range(start, end, True, True)

        # Schedule message
        send_dt = start - timedelta(minutes=settings_manager.get_setting('setup_time_mins') + settings_manager.get_setting('quartermaster_reminder_time_mins'))
        request_names = [request['name'] for request in requests]
        job_id = f'request code msg {send_dt.strftime("%Y-%m-%d %H:%M:%S")}'
        print(f'[schedule_request_msg] Scheduling {job_id}: after={after!r}, request_start={start.isoformat()}, request_range_end={end.isoformat()}, run_date={send_dt.isoformat()}, callback_msg_time={send_dt.time().isoformat()} (hour={send_dt.hour}), requests={request_names}')
        band_msg_scheduler.add_job(request_code_msg, 'date', run_date=send_dt,
                                   args=[requests, send_dt.time()], id=job_id, replace_existing=True)
    else:
        print(f'[schedule_request_msg] No request message scheduled: no request found after={after!r}.')


def schedule_change_reminder_msg():
    """Schedules message to the Quartermaster to change the lockbox code and what to change it to."""
    existing_jobs = [
        (job.id, job.next_run_time.isoformat() if getattr(job, 'next_run_time', None) is not None else None)
        for job in qm_msg_scheduler.get_jobs()
        if job.id.startswith(('change reminder ', 'change re-reminder '))
    ]
    print(f'[schedule_change_reminder_msg] Existing code-reminder jobs before scheduling: {existing_jobs}')
    for job_id, _ in existing_jobs:
        qm_msg_scheduler.remove_job(job_id)
        print(f'[schedule_change_reminder_msg] Removed outdated code-reminder job {job_id!r}.')

    expires = code_manager.get_expires()
    now_local = datetime.now(tz=settings_manager.get_timezone())
    if expires >= now_local.date():
        normalized_expires = code_manager.normalize_stored_expiration_date()
        if normalized_expires != expires:
            print(f'[schedule_change_reminder_msg] Adjusting stored expiration date from {expires.isoformat()} to {normalized_expires.isoformat()} to honor the weekend setting.')
            expires = normalized_expires

    reminder_time = settings_manager.get_change_code_reminder_time()
    send_dt = datetime.combine(expires, reminder_time)
    now = datetime.now(tz=timezone.utc)
    job_id = f'change reminder {send_dt.strftime("%Y-%m-%d %H:%M:%S")}'
    callback_time = send_dt.time()
    print(f'[schedule_change_reminder_msg] expires={expires.isoformat()}, configured_time={reminder_time.isoformat()}, timezone={reminder_time.tzinfo}, run_date={send_dt.isoformat()}, callback_msg_time={callback_time.isoformat()} (hour={callback_time.hour}, tzinfo={callback_time.tzinfo!r}), now_utc={now.isoformat()}')
    if send_dt > now:
        print(f'[schedule_change_reminder_msg] Scheduling {job_id}.')
        qm_msg_scheduler.add_job(change_reminder_msg, 'date', run_date=send_dt, args=[send_dt.time()], id=job_id, replace_existing=True)
    else:
        print(f'[schedule_change_reminder_msg] Skipping {job_id}: run_date is not later than now_utc.')
    schedule_change_re_reminder_msg()


def schedule_change_re_reminder_msg():
    """Schedules message to the Quartermaster to re-remind quartermaster to change lockbox code and what to change it to."""
    delay_hours = settings_manager.get_setting('change_code_re-reminder_hours')
    if delay_hours == 0:
        print('[schedule_change_re_reminder_msg] Re-reminder disabled: delay_hours=0.')
        return # Re-reminder disabled
    existing_jobs = [
        (job.id, job.next_run_time.isoformat() if getattr(job, 'next_run_time', None) is not None else None)
        for job in qm_msg_scheduler.get_jobs()
        if job.id.startswith(('change reminder ', 'change re-reminder '))
    ]
    print(f'[schedule_change_re_reminder_msg] Existing code-reminder jobs before scheduling: {existing_jobs}')
    expires = code_manager.get_expires()
    reminder_time = settings_manager.get_change_code_reminder_time()
    send_dt = datetime.combine(expires, reminder_time) + timedelta(hours=delay_hours)
    now = datetime.now(tz=timezone.utc)
    job_id = f'change re-reminder {send_dt.strftime("%Y-%m-%d %H:%M:%S")}'
    callback_time = send_dt.time()
    print(f'[schedule_change_re_reminder_msg] expires={expires.isoformat()}, configured_time={reminder_time.isoformat()}, timezone={reminder_time.tzinfo}, delay_hours={delay_hours}, run_date={send_dt.isoformat()}, callback_msg_time={callback_time.isoformat()} (hour={callback_time.hour}, tzinfo={callback_time.tzinfo!r}), now_utc={now.isoformat()}')
    if send_dt > now:
        print(f'[schedule_change_re_reminder_msg] Scheduling {job_id}.')
        qm_msg_scheduler.add_job(change_re_reminder_msg, 'date', run_date=send_dt, args=[send_dt.time()], id=job_id, replace_existing=True)
    else:
        print(f'[schedule_change_re_reminder_msg] Skipping {job_id}: run_date is not later than now_utc.')


def schedule_refresh_calendar(update_dt=None):
    """Schedules the update of scheduled messages."""
    if update_dt is None:
        update_dt = datetime.now(tz=timezone.utc) + timedelta(minutes=settings_manager.get_setting('calendar_refresh_mins'))
        # Truncate time to minutes to prevent drift
        update_dt = update_dt.replace(second=0, microsecond=0)

    job_id = f'calendar update {update_dt.strftime("%Y-%m-%d %H:%M:%S")}'
    print(f'[schedule_refresh_calendar] Scheduling {job_id}: run_date={update_dt.isoformat()}, callback_args={[True]}')
    update_scheduler.add_job(refresh_calendar, 'date', run_date=update_dt, args=[True], id=job_id, replace_existing=True)


async def band_greeting_msg(band):
    channel = client.get_channel(band['channel_id'])
    msg = content_manager.format_message(content_manager.get_message('band greeting'), datetime.now(), {'band': band['name'], 'name': client.user.display_name, 'url': settings_manager.get_setting('gear_calendar_url')}, band['role'])

    try:
        await channel.send(msg)
        return None
    except discord.errors.Forbidden:
        return f"No access to band's channel"


client.run(token)