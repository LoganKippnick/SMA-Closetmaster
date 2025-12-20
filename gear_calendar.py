import os.path

from datetime import datetime, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import band_manager
import settings_manager

# If modifying these scopes, delete the file calendar_token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

gear_calendar_id = settings_manager.get_setting('gear_calendar_id')
tz = settings_manager.get_timezone()


def format_rehearsal_event(request):
    name = request['summary']
    event = name.split(' ')[-1].lower()
    band = ' '.join(name.split(' ')[:-1])

    if event != 'rehearsal' or 'dateTime' not in request['start'] or band_manager.get_band(band) is None:
        return None

    start = datetime.fromisoformat(request['start']['dateTime']).astimezone(tz)
    end = datetime.fromisoformat(request['end']['dateTime']).astimezone(tz)

    return {'name': name, 'band': band, 'event': event, 'start': start, 'end': end}


def format_request_event(request):
    name = request['summary']

    if 'dateTime' not in request['start']:
        return None

    start = datetime.fromisoformat(request['start']['dateTime']).astimezone(tz)
    end = datetime.fromisoformat(request['end']['dateTime']).astimezone(tz)

    return {'name': name, 'start': start, 'end': end}


def get_calendar_items(time_min=None, time_max=None):
    if time_min is None:
        time_min = datetime.now(tz=timezone.utc)

    creds = None
    # The file calendar_token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("calendar_token.json"):
        creds = Credentials.from_authorized_user_file("calendar_token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "calendar_creds.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("calendar_token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("calendar", "v3", credentials=creds)

        # Call the Calendar API
        if time_max is None:
            return (
                service.events()
                .list(
                    calendarId=gear_calendar_id,
                    timeMin=time_min.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            ).get('items', [])
        else:
            return (
                service.events()
                .list(
                    calendarId=gear_calendar_id,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            ).get('items', [])

    except HttpError as error:
        print(f"An error occurred: {error}")


def get_next_events(after=None):
    if after is None:
        after = datetime.now(tz=timezone.utc)
    else:
        after = after.astimezone(tz=timezone.utc)
    after += timedelta(seconds=1)

    items = get_calendar_items(after)
    events = []

    for i in range(len(items)):
        if datetime.fromisoformat(items[i]['start']['dateTime']) >= after:
            events = items[i:]
            break

    return events


def get_curr_events(date=None):
    if date is None:
        date = datetime.now(tz=timezone.utc)

    print(date.isoformat())

    items = get_calendar_items(date)
    events = []

    for i in range(len(items)):
        print(items[i]['end']['dateTime'], end='\t')
        if datetime.fromisoformat(items[i]['start']['dateTime']) > date:
            events = items[:i]
            print(i)
            break
        else:
            print(False)

    return events


def get_next_rehearsal(after=None):
    requests = []

    next_events = get_next_events(after)

    for request in next_events:
        rehearsal = format_rehearsal_event(request)
        if rehearsal is not None:
            if len(requests) == 0 or requests[0]['start'] == rehearsal['start']:
                requests.append(rehearsal)
            else:
                break

    return requests


def get_curr_rehearsal(date=None):
    requests = []

    curr_events = get_curr_events(date)

    for request in curr_events:
        rehearsal = format_rehearsal_event(request)
        if rehearsal is not None:
            requests.append(rehearsal)

    return requests


def get_requests_in_range(start, end, include_start=False, include_end=False):
    if include_start:
        start -= timedelta(seconds=1)

    if include_end:
        end += timedelta(seconds=1)

    events = get_calendar_items(start, end)

    requests = []

    for event in events:
        if 'summary' not in event:
            print(event)
        request = format_request_event(event)
        if request is not None:
            requests.append(request)

    return requests


def get_next_request(after=None):
    requests = []

    next_events = get_next_events(after)

    for event in next_events:
        if format_rehearsal_event(event) is None:
            request = format_request_event(event)
            if request is not None:
                if len(requests) == 0 or requests[0]['start'] == request['start']:
                    requests.append(request)
                else:
                    break

    return requests