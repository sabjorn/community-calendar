import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Response
from icalendar import Calendar

from ..utilities import add_event_to_calendar, remove_past_events

router = APIRouter(
    tags=["calendar"],
    responses={404: {"description": "Not found"}},
)

ICS_FILE_PATH = Path('/var/www/html/events.ics')

@dataclass
class EventCreate():
    title: str
    start_time: datetime
    end_time: datetime
    description: str
    venue: str
    url: str = ""

@router.post("/add-event")
async def add_event(event: EventCreate):
    event_data = {
        'title': event.title,
        'start_time': event.start_time,
        'end_time': event.end_time,
        'description': event.description,
        'venue': event.venue,
        'url': event.url
    }
    
    add_event_to_calendar(ICS_FILE_PATH, event_data)
    
    return {"message": "Event added successfully"}

@router.get("/events.ics")
async def get_calendar():
    #if not os.path.exists(ICS_FILE_PATH):
    #    cal = Calendar()
    #    cal.add('prodid', '-//Dance Events Calendar//EN')
    #    cal.add('version', '2.0')
    #    with open(ICS_FILE_PATH, 'wb') as f:
    #        f.write(cal.to_ical())
    
    calendar = Calendar.from_ical(ICS_FILE_PATH.read_bytes())
    return Response(calendar.to_ical(), media_type="text/calendar", 
                   headers={"Content-Disposition": "attachment; filename=events.ics"})

@router.post("/cleanup")
async def cleanup_past_events():
    #remove_past_events(ICS_FILE_PATH)
    return {"message": "Past events cleaned up"}
