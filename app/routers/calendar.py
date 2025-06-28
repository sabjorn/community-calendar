import secrets
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from icalendar import Calendar, Event as ICalEvent
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Event, get_db, create_tables

router = APIRouter(
    tags=["calendar"],
    responses={404: {"description": "Not found"}},
)

security = HTTPBasic()

def authenticate_user(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, settings.auth_username)
    correct_password = secrets.compare_digest(credentials.password, settings.auth_password)
    if not (correct_username and correct_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return credentials.username

class EventCreate(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    description: str
    venue: str
    url: str = ""
    tags: List[str] = []

@router.post("/add-event")
async def add_event(event: EventCreate, db: Session = Depends(get_db)):
    db_event = Event(
        title=event.title,
        start_time=event.start_time,
        end_time=event.end_time,
        description=event.description,
        venue=event.venue,
        url=event.url
    )
    db_event.set_tags_list(event.tags)
    
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    return {"message": "Event added successfully", "event_id": db_event.id}

@router.get("/events.ics")
async def get_calendar(db: Session = Depends(get_db)):
    cal = Calendar()
    cal.add('prodid', settings.calendar_prodid)
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    
    events = db.query(Event).all()
    
    for event in events:
        ical_event = ICalEvent()
        ical_event.add('uid', str(uuid.uuid4()))
        ical_event.add('dtstart', event.start_time)
        ical_event.add('dtend', event.end_time)
        ical_event.add('summary', event.title)
        ical_event.add('description', event.description)
        ical_event.add('location', event.venue)
        ical_event.add('url', event.url)
        ical_event.add('dtstamp', datetime.now(timezone.utc))
        ical_event.add('created', datetime.now(timezone.utc))
        
        cal.add_component(ical_event)
    
    return Response(cal.to_ical(), media_type="text/calendar", 
                   headers={"Content-Disposition": "attachment; filename=events.ics"})

@router.post("/cleanup")
async def cleanup_past_events(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    past_events = db.query(Event).filter(Event.end_time < now).all()
    
    for event in past_events:
        db.delete(event)
    
    db.commit()
    return {"message": f"Removed {len(past_events)} past events"}

@router.get("/submit-event", response_class=HTMLResponse)
async def submit_event_form(username: str = Depends(authenticate_user)):
    form_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Submit Event</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            textarea { height: 100px; resize: vertical; }
            button { background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background-color: #0056b3; }
            .error { color: red; margin-top: 10px; }
        </style>
    </head>
    <body>
        <h1>Submit Event</h1>
        <form method="post" action="/submit-event">
            <div class="form-group">
                <label for="title">Title:</label>
                <input type="text" id="title" name="title" required>
            </div>
            <div class="form-group">
                <label for="start_time">Start Time:</label>
                <input type="datetime-local" id="start_time" name="start_time" required>
            </div>
            <div class="form-group">
                <label for="end_time">End Time:</label>
                <input type="datetime-local" id="end_time" name="end_time" required>
            </div>
            <div class="form-group">
                <label for="description">Description:</label>
                <textarea id="description" name="description" required></textarea>
            </div>
            <div class="form-group">
                <label for="venue">Venue:</label>
                <input type="text" id="venue" name="venue" required>
            </div>
            <div class="form-group">
                <label for="url">URL:</label>
                <input type="url" id="url" name="url">
            </div>
            <div class="form-group">
                <label for="tags">Tags (comma-separated):</label>
                <input type="text" id="tags" name="tags" placeholder="e.g., music, outdoor, family">
            </div>
            <button type="submit">Submit Event</button>
        </form>
    </body>
    </html>
    """
    return form_html

@router.post("/submit-event", response_class=HTMLResponse)
async def submit_event_form_post(
    title: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    description: str = Form(...),
    venue: str = Form(...),
    url: str = Form(""),
    tags: str = Form(""),
    username: str = Depends(authenticate_user),
    db: Session = Depends(get_db)
):
    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
        
        tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        db_event = Event(
            title=title,
            start_time=start_dt,
            end_time=end_dt,
            description=description,
            venue=venue,
            url=url
        )
        db_event.set_tags_list(tags_list)
        
        db.add(db_event)
        db.commit()
        
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Event Submitted</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                .success { color: green; }
                a { color: #007bff; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <h1>Event Submitted Successfully!</h1>
            <p class="success">Your event has been added to the calendar.</p>
            <p><a href="/submit-event">Submit another event</a></p>
        </body>
        </html>
        """
        
    except ValueError as e:
        error_message = f"Invalid date format: {str(e)}"
    except Exception as e:
        error_message = f"Error submitting event: {str(e)}"
    
    form_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Submit Event</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
            .form-group {{ margin-bottom: 15px; }}
            label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
            input, textarea {{ width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }}
            textarea {{ height: 100px; resize: vertical; }}
            button {{ background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }}
            button:hover {{ background-color: #0056b3; }}
            .error {{ color: red; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <h1>Submit Event</h1>
        <div class="error">{error_message}</div>
        <form method="post" action="/submit-event">
            <div class="form-group">
                <label for="title">Title:</label>
                <input type="text" id="title" name="title" value="{title}" required>
            </div>
            <div class="form-group">
                <label for="start_time">Start Time:</label>
                <input type="datetime-local" id="start_time" name="start_time" value="{start_time}" required>
            </div>
            <div class="form-group">
                <label for="end_time">End Time:</label>
                <input type="datetime-local" id="end_time" name="end_time" value="{end_time}" required>
            </div>
            <div class="form-group">
                <label for="description">Description:</label>
                <textarea id="description" name="description" required>{description}</textarea>
            </div>
            <div class="form-group">
                <label for="venue">Venue:</label>
                <input type="text" id="venue" name="venue" value="{venue}" required>
            </div>
            <div class="form-group">
                <label for="url">URL:</label>
                <input type="url" id="url" name="url" value="{url}">
            </div>
            <div class="form-group">
                <label for="tags">Tags (comma-separated):</label>
                <input type="text" id="tags" name="tags" value="{tags}" placeholder="e.g., music, outdoor, family">
            </div>
            <button type="submit">Submit Event</button>
        </form>
    </body>
    </html>
    """
    return form_html
