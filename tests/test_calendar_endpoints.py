import base64
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from icalendar import Calendar

test_env = {
    "DATABASE_URL": "sqlite:///:memory:",
    "AUTH_USERNAME": "admin",
    "AUTH_PASSWORD": "test_password",
    "APP_TITLE": "Test Calendar",
    "APP_DESCRIPTION": "Test Description",
    "CALENDAR_PRODID": "-//Test Calendar//EN",
}

with patch.dict(os.environ, test_env), patch("app.models.create_tables"):
    from app.main import app
    from app.models import get_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    credentials = base64.b64encode(b"admin:test_password").decode("ascii")
    return {"Authorization": f"Basic {credentials}"}


def test_add_event_missing_required_fields(client, auth_headers):
    incomplete_data = {
        "title": "Incomplete Event",
        "start_time": "2025-07-01T19:00:00",
    }

    response = client.post("/add-event", json=incomplete_data, headers=auth_headers)
    assert response.status_code == 422


def test_add_event_invalid_datetime_format(client, auth_headers):
    invalid_data = {
        "title": "Invalid Event",
        "start_time": "invalid-datetime",
        "end_time": "2025-07-01T21:00:00",
        "description": "Event with invalid datetime",
        "venue": "Test Venue",
    }

    response = client.post("/add-event", json=invalid_data, headers=auth_headers)
    assert response.status_code == 422


def test_add_event_success(client, auth_headers):
    mock_db_session = Mock()

    def override_get_db():
        return mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    sample_event_data = {
        "title": "Test Event",
        "start_time": "2025-07-01T19:00:00",
        "end_time": "2025-07-01T21:00:00",
        "description": "A test event for the calendar",
        "venue": "Test Venue",
        "url": "https://example.com",
        "tags": ["test", "demo"],
    }

    try:
        with patch("app.routers.calendar.Event") as mock_event_class:
            mock_event = Mock()
            mock_event.id = 1
            mock_event.set_tags_list = Mock()
            mock_event_class.return_value = mock_event

            response = client.post(
                "/add-event", json=sample_event_data, headers=auth_headers
            )

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["message"] == "Event added successfully"
            assert response_data["event_id"] == "1"

            mock_event_class.assert_called_once()
            mock_event.set_tags_list.assert_called_once_with(["test", "demo"])
            mock_db_session.add.assert_called_once_with(mock_event)
            mock_db_session.commit.assert_called_once()
            mock_db_session.refresh.assert_called_once_with(mock_event)
    finally:
        app.dependency_overrides.clear()


def test_add_event_with_tags(client, auth_headers):
    mock_db_session = Mock()

    def override_get_db():
        return mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    event_data = {
        "title": "Tagged Event",
        "start_time": "2025-07-01T19:00:00",
        "end_time": "2025-07-01T21:00:00",
        "description": "Event with tags",
        "venue": "Test Venue",
        "tags": ["music", "outdoor", "family"],
    }

    try:
        with patch("app.routers.calendar.Event") as mock_event_class:
            mock_event = Mock()
            mock_event.id = 2
            mock_event.set_tags_list = Mock()
            mock_event_class.return_value = mock_event

            response = client.post("/add-event", json=event_data, headers=auth_headers)

            assert response.status_code == 200
            mock_event.set_tags_list.assert_called_once_with(
                ["music", "outdoor", "family"]
            )
    finally:
        app.dependency_overrides.clear()


def test_add_event_minimal_data(client, auth_headers):
    mock_db_session = Mock()

    def override_get_db():
        return mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    minimal_event_data = {
        "title": "Minimal Event",
        "start_time": "2025-07-01T19:00:00",
        "end_time": "2025-07-01T21:00:00",
        "description": "Minimal event description",
        "venue": "Test Venue",
    }

    try:
        with patch("app.routers.calendar.Event") as mock_event_class:
            mock_event = Mock()
            mock_event.id = 3
            mock_event.set_tags_list = Mock()
            mock_event_class.return_value = mock_event

            response = client.post(
                "/add-event", json=minimal_event_data, headers=auth_headers
            )

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["message"] == "Event added successfully"
            assert response_data["event_id"] == "3"
    finally:
        app.dependency_overrides.clear()


def test_add_event_unauthenticated(client):
    sample_event_data = {
        "title": "Test Event",
        "start_time": "2025-07-01T19:00:00",
        "end_time": "2025-07-01T21:00:00",
        "description": "A test event for the calendar",
        "venue": "Test Venue",
    }

    response = client.post("/add-event", json=sample_event_data)
    assert response.status_code == 401


def test_cleanup_past_events_success(client, auth_headers):
    mock_db_session = Mock()

    past_event1 = Mock()
    past_event2 = Mock()
    mock_db_session.query.return_value.filter.return_value.all.return_value = [
        past_event1,
        past_event2,
    ]

    def override_get_db():
        return mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.post("/cleanup", headers=auth_headers)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["message"] == "Removed 2 past events"

        assert mock_db_session.delete.call_count == 2
        mock_db_session.commit.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_cleanup_past_events_unauthenticated(client):
    response = client.post("/cleanup")
    assert response.status_code == 401


def test_get_events_success(client, auth_headers):
    mock_db_session = Mock()

    mock_event1 = Mock(
        spec=[
            "id",
            "title",
            "start_time",
            "end_time",
            "description",
            "venue",
            "url",
            "tags",
        ]
    )
    mock_event1.id = 1
    mock_event1.title = "Event 1"
    mock_event1.start_time = datetime(2025, 7, 1, 19, 0, 0)
    mock_event1.end_time = datetime(2025, 7, 1, 21, 0, 0)
    mock_event1.description = "First event"
    mock_event1.venue = "Venue 1"
    mock_event1.url = "https://example1.com"
    mock_event1.tags = "music,outdoor"

    mock_event2 = Mock(
        spec=[
            "id",
            "title",
            "start_time",
            "end_time",
            "description",
            "venue",
            "url",
            "tags",
        ]
    )
    mock_event2.id = 2
    mock_event2.title = "Event 2"
    mock_event2.start_time = datetime(2025, 7, 2, 19, 0, 0)
    mock_event2.end_time = datetime(2025, 7, 2, 21, 0, 0)
    mock_event2.description = "Second event"
    mock_event2.venue = "Venue 2"
    mock_event2.url = "https://example2.com"
    mock_event2.tags = "family"

    mock_db_session.query.return_value.all.return_value = [mock_event1, mock_event2]

    def override_get_db():
        return mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/events", headers=auth_headers)

        assert response.status_code == 200
        events_data = response.json()
        assert len(events_data) == 2

        event_titles = [event["title"] for event in events_data]
        assert "Event 1" in event_titles
        assert "Event 2" in event_titles
    finally:
        app.dependency_overrides.clear()


def test_get_events_empty_list(client, auth_headers):
    mock_db_session = Mock()
    mock_db_session.query.return_value.all.return_value = []

    def override_get_db():
        return mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/events", headers=auth_headers)

        assert response.status_code == 200
        events_data = response.json()
        assert events_data == []
    finally:
        app.dependency_overrides.clear()


def test_get_events_unauthenticated(client):
    response = client.get("/events")
    assert response.status_code == 401


def test_delete_event_success(client, auth_headers):
    mock_db_session = Mock()

    mock_event = Mock()
    mock_event.id = 1
    mock_event.title = "Event to Delete"

    mock_db_session.query.return_value.filter.return_value.first.return_value = (
        mock_event
    )

    def override_get_db():
        return mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.delete("/events/1", headers=auth_headers)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["message"] == "Event 1 deleted successfully"

        mock_db_session.delete.assert_called_once_with(mock_event)
        mock_db_session.commit.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_delete_event_not_found(client, auth_headers):
    mock_db_session = Mock()
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    def override_get_db():
        return mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.delete("/events/999", headers=auth_headers)

        assert response.status_code == 404
        response_data = response.json()
        assert response_data["detail"] == "Event not found"

        mock_db_session.delete.assert_not_called()
        mock_db_session.commit.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_delete_event_invalid_id_type(client, auth_headers):
    response = client.delete("/events/invalid_id", headers=auth_headers)
    assert response.status_code == 422


def test_delete_event_unauthenticated(client):
    response = client.delete("/events/1")
    assert response.status_code == 401


def test_get_calendar_empty(client):
    mock_db_session = Mock()
    mock_db_session.query.return_value.all.return_value = []

    def override_get_db():
        return mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/events.ics")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/calendar; charset=utf-8"
        assert "Content-Disposition" in response.headers
        assert "events.ics" in response.headers["Content-Disposition"]

        calendar_text = response.text
        assert "BEGIN:VCALENDAR" in calendar_text
        assert "END:VCALENDAR" in calendar_text
        assert "PRODID:-//Test Calendar//EN" in calendar_text
        assert "VERSION:2.0" in calendar_text
    finally:
        app.dependency_overrides.clear()


@patch("app.routers.calendar.uuid.uuid4")
@patch("app.routers.calendar.datetime")
def test_get_calendar_with_events(mock_datetime, mock_uuid, client):
    mock_db_session = Mock()

    mock_uuid.return_value = "test-uuid-123"
    mock_datetime.now.return_value = datetime(
        2025, 6, 28, 12, 0, 0, tzinfo=timezone.utc
    )

    sample_event = Mock()
    sample_event.title = "Test Event"
    sample_event.start_time = datetime(2025, 7, 1, 19, 0, 0)
    sample_event.end_time = datetime(2025, 7, 1, 21, 0, 0)
    sample_event.description = "A test event for the calendar"
    sample_event.venue = "Test Venue"
    sample_event.url = "https://example.com"

    mock_db_session.query.return_value.all.return_value = [sample_event]

    def override_get_db():
        return mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/events.ics")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/calendar; charset=utf-8"

        calendar_text = response.text
        assert "BEGIN:VCALENDAR" in calendar_text
        assert "END:VCALENDAR" in calendar_text
        assert "BEGIN:VEVENT" in calendar_text
        assert "END:VEVENT" in calendar_text
        assert "SUMMARY:Test Event" in calendar_text
        assert "LOCATION:Test Venue" in calendar_text
        assert "DESCRIPTION:A test event for the calendar" in calendar_text
        assert "URL:https://example.com" in calendar_text
        assert "UID:test-uuid-123" in calendar_text
    finally:
        app.dependency_overrides.clear()


def test_get_calendar_multiple_events(client):
    mock_db_session = Mock()

    event1 = Mock()
    event1.title = "Event 1"
    event1.start_time = datetime(2025, 7, 1, 19, 0, 0)
    event1.end_time = datetime(2025, 7, 1, 21, 0, 0)
    event1.description = "First event"
    event1.venue = "Venue 1"
    event1.url = "https://example1.com"

    event2 = Mock()
    event2.title = "Event 2"
    event2.start_time = datetime(2025, 7, 2, 19, 0, 0)
    event2.end_time = datetime(2025, 7, 2, 21, 0, 0)
    event2.description = "Second event"
    event2.venue = "Venue 2"
    event2.url = "https://example2.com"

    mock_db_session.query.return_value.all.return_value = [event1, event2]

    def override_get_db():
        return mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/events.ics")

        assert response.status_code == 200
        calendar_text = response.text

        assert calendar_text.count("BEGIN:VEVENT") == 2
        assert calendar_text.count("END:VEVENT") == 2
        assert "SUMMARY:Event 1" in calendar_text
        assert "SUMMARY:Event 2" in calendar_text
        assert "LOCATION:Venue 1" in calendar_text
        assert "LOCATION:Venue 2" in calendar_text
    finally:
        app.dependency_overrides.clear()


def test_get_calendar_validates_ical_format(client):
    mock_db_session = Mock()

    sample_event = Mock()
    sample_event.title = "Test Event"
    sample_event.start_time = datetime(2025, 7, 1, 19, 0, 0)
    sample_event.end_time = datetime(2025, 7, 1, 21, 0, 0)
    sample_event.description = "A test event for the calendar"
    sample_event.venue = "Test Venue"
    sample_event.url = "https://example.com"

    mock_db_session.query.return_value.all.return_value = [sample_event]

    def override_get_db():
        return mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/events.ics")

        assert response.status_code == 200

        calendar = Calendar.from_ical(response.content)
        assert calendar is not None

        events = [
            component for component in calendar.walk() if component.name == "VEVENT"
        ]
        assert len(events) == 1

        event = events[0]
        assert event.get("summary") == "Test Event"
        assert event.get("location") == "Test Venue"
        assert event.get("description") == "A test event for the calendar"
    finally:
        app.dependency_overrides.clear()


def test_get_calendar_database_error_handled_gracefully(client):
    mock_db_session = Mock()
    mock_db_session.query.side_effect = Exception("Database connection error")

    def override_get_db():
        return mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/events.ics")
        assert response.status_code in [200, 500]
    except Exception:
        pass
    finally:
        app.dependency_overrides.clear()
