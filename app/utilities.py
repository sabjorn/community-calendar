import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from icalendar import Calendar, Event

def add_event_to_calendar(ics_file_path: Path, event_data):
    if os.path.exists(ics_file_path):
        cal = Calendar.from_ical(ics_file_path.read_bytes())
    else:
        cal = Calendar()
        cal.add('prodid', '-//Dance Events Calendar//EN')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
    
    event = Event()
    event.add('uid', str(uuid.uuid4()))
    event.add('dtstart', event_data['start_time'])
    event.add('dtend', event_data['end_time'])
    event.add('summary', event_data['title'])
    event.add('description', event_data['description'])
    event.add('location', event_data['venue'])
    event.add('url', event_data.get('url', ''))
    event.add('dtstamp', datetime.now(timezone.utc))
    event.add('created', datetime.now(timezone.utc))
    
    cal.add_component(event)
    
    ics_file_path.write_bytes(cal.to_ical())

def remove_past_events(ics_file_path: Path):
    if not os.path.exists(ics_file_path):
        return
        
    cal = Calendar.from_ical(ics_file_path.read_bytes())

    new_cal = Calendar()
    new_cal.add('prodid', '-//Dance Events Calendar//EN')
    new_cal.add('version', '2.0')
    new_cal.add('calscale', 'GREGORIAN')
    new_cal.add('method', 'PUBLISH')
    
    now = datetime.now(timezone.utc)
    
    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        event_start = component.get('dtstart').dt
        if event_start < now:
            continue

        new_cal.add_component(component)
    
    ics_file_path.write_bytes(new_cal.to_ical())
