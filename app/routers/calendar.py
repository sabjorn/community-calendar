import html
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from icalendar import Calendar, Event as ICalEvent
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Event, get_db

router = APIRouter(
    tags=["calendar"],
    responses={404: {"description": "Not found"}},
)

security = HTTPBasic()


def authenticate_user(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    correct_username = secrets.compare_digest(
        credentials.username, settings.auth_username
    )
    correct_password = secrets.compare_digest(
        credentials.password, settings.auth_password
    )
    if not (correct_username and correct_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return credentials.username


class EventCreate(BaseModel):
    title: str = Field(..., max_length=200, min_length=1)
    start_time: datetime
    end_time: datetime
    description: str = Field(..., max_length=2000, min_length=1)
    venue: str = Field(..., max_length=200, min_length=1)
    url: str = Field("", max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        if len(v) > 10:
            raise ValueError("Maximum 10 tags allowed")
        validated_tags = []
        for tag in v:
            if len(tag) > 50:
                raise ValueError("Tag length cannot exceed 50 characters")
            sanitized_tag = html.escape(tag.strip())
            if sanitized_tag:
                validated_tags.append(sanitized_tag)
        return validated_tags

    @field_validator("title", "description", "venue")
    @classmethod
    def sanitize_text_fields(cls, v):
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return html.escape(v.strip())

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        if v:
            return html.escape(v.strip())
        return v


@router.post("/add-event")
async def add_event(
    event: EventCreate,
    db: Session = Depends(get_db),
    _: str = Depends(authenticate_user),
) -> dict[str, str]:
    db_event = Event(
        title=event.title,
        start_time=event.start_time,
        end_time=event.end_time,
        description=event.description,
        venue=event.venue,
        url=event.url,
    )
    db_event.set_tags_list(event.tags)

    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    return {"message": "Event added successfully", "event_id": str(db_event.id)}


@router.get("/events.ics")
async def get_calendar(db: Session = Depends(get_db)) -> Response:
    cal = Calendar()
    cal.add("prodid", settings.calendar_prodid)
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")

    events = db.query(Event).all()

    for event in events:
        ical_event = ICalEvent()
        ical_event.add("uid", str(uuid.uuid4()))
        ical_event.add("dtstart", event.start_time)
        ical_event.add("dtend", event.end_time)
        ical_event.add("summary", event.title)
        ical_event.add("description", event.description)
        ical_event.add("location", event.venue)
        ical_event.add("url", event.url)
        ical_event.add("dtstamp", datetime.now(timezone.utc))
        ical_event.add("created", datetime.now(timezone.utc))

        cal.add_component(ical_event)

    return Response(
        cal.to_ical(),
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=events.ics"},
    )


@router.post("/cleanup")
async def cleanup_past_events(
    db: Session = Depends(get_db), _: str = Depends(authenticate_user)
) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    past_events = db.query(Event).filter(Event.end_time < now).all()

    for event in past_events:
        db.delete(event)

    db.commit()
    return {"message": f"Removed {len(past_events)} past events"}


@router.get("/submit-event", response_class=HTMLResponse)
async def submit_event_form(
    _: str = Depends(authenticate_user),
    success: str | None = None,
    error: str | None = None,
) -> str:
    message_html = ""
    if success:
        message_html = '<div class="success">Event submitted successfully! <a href="/submit-event">Submit another event</a></div>'
    elif error:
        message_html = (
            '<div class="error">Error submitting event. Please try again.</div>'
        )

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
            .error {{ color: red; margin-bottom: 15px; }}
            .success {{ color: green; margin-bottom: 15px; }}
            a {{ color: #007bff; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <h1>Submit Event</h1>
        {message_html}
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


@router.post("/submit-event")
async def submit_event_form_post(
    title: str = Form(..., max_length=200),
    start_time: str = Form(...),
    end_time: str = Form(...),
    description: str = Form(..., max_length=2000),
    venue: str = Form(..., max_length=200),
    url: str = Form("", max_length=500),
    tags: str = Form("", max_length=500),
    _: str = Depends(authenticate_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)

        if start_dt >= end_dt:
            return RedirectResponse(url="/submit-event?error=1", status_code=303)

        sanitized_title = html.escape(title.strip())
        sanitized_description = html.escape(description.strip())
        sanitized_venue = html.escape(venue.strip())
        sanitized_url = html.escape(url.strip()) if url else ""

        tags_list = []
        if tags:
            raw_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
            if len(raw_tags) > 10:
                return RedirectResponse(url="/submit-event?error=1", status_code=303)
            tags_list = [html.escape(tag)[:50] for tag in raw_tags[:10]]

        db_event = Event(
            title=sanitized_title,
            start_time=start_dt,
            end_time=end_dt,
            description=sanitized_description,
            venue=sanitized_venue,
            url=sanitized_url,
        )
        db_event.set_tags_list(tags_list)

        db.add(db_event)
        db.commit()

        return RedirectResponse(url="/submit-event?success=1", status_code=303)

    except Exception:
        return RedirectResponse(url="/submit-event?error=1", status_code=303)
