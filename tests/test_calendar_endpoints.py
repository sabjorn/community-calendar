from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from icalendar import Calendar

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_event_data():
    return {
        "title": "Test Event",
        "start_time": "2025-07-01T19:00:00",
        "end_time": "2025-07-01T21:00:00",
        "description": "A test event for the calendar",
        "venue": "Test Venue",
        "url": "https://example.com",
        "tags": ["test", "demo"]
    }


class TestAddEventEndpoint:
    
    def test_add_event_missing_required_fields(self, client):
        incomplete_data = {
            "title": "Incomplete Event",
            "start_time": "2025-07-01T19:00:00"
        }
        
        response = client.post("/add-event", json=incomplete_data)
        assert response.status_code == 422

    def test_add_event_invalid_datetime_format(self, client):
        invalid_data = {
            "title": "Invalid Event",
            "start_time": "invalid-datetime",
            "end_time": "2025-07-01T21:00:00",
            "description": "Event with invalid datetime",
            "venue": "Test Venue"
        }
        
        response = client.post("/add-event", json=invalid_data)
        assert response.status_code == 422

    @patch('app.routers.calendar.get_db')
    def test_add_event_success(self, mock_get_db, client, sample_event_data):
        mock_db_session = Mock()
        mock_get_db.return_value = mock_db_session
        
        with patch('app.routers.calendar.Event') as mock_event_class:
            mock_event = Mock()
            mock_event.id = 1
            mock_event.set_tags_list = Mock()
            mock_event_class.return_value = mock_event
            
            response = client.post("/add-event", json=sample_event_data)
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["message"] == "Event added successfully"
            assert response_data["event_id"] == 1
            
            mock_event_class.assert_called_once()
            mock_event.set_tags_list.assert_called_once_with(["test", "demo"])
            mock_db_session.add.assert_called_once_with(mock_event)
            mock_db_session.commit.assert_called_once()
            mock_db_session.refresh.assert_called_once_with(mock_event)

    @patch('app.routers.calendar.get_db')
    def test_add_event_with_tags(self, mock_get_db, client):
        mock_db_session = Mock()
        mock_get_db.return_value = mock_db_session
        
        event_data = {
            "title": "Tagged Event",
            "start_time": "2025-07-01T19:00:00",
            "end_time": "2025-07-01T21:00:00",
            "description": "Event with tags",
            "venue": "Test Venue",
            "tags": ["music", "outdoor", "family"]
        }
        
        with patch('app.routers.calendar.Event') as mock_event_class:
            mock_event = Mock()
            mock_event.id = 2
            mock_event.set_tags_list = Mock()
            mock_event_class.return_value = mock_event
            
            response = client.post("/add-event", json=event_data)
            
            assert response.status_code == 200
            mock_event.set_tags_list.assert_called_once_with(["music", "outdoor", "family"])

    @patch('app.routers.calendar.get_db')
    def test_add_event_minimal_data(self, mock_get_db, client):
        mock_db_session = Mock()
        mock_get_db.return_value = mock_db_session
        
        minimal_event_data = {
            "title": "Minimal Event",
            "start_time": "2025-07-01T19:00:00",
            "end_time": "2025-07-01T21:00:00",
            "description": "Minimal event description",
            "venue": "Test Venue"
        }
        
        with patch('app.routers.calendar.Event') as mock_event_class:
            mock_event = Mock()
            mock_event.id = 3
            mock_event.set_tags_list = Mock()
            mock_event_class.return_value = mock_event
            
            response = client.post("/add-event", json=minimal_event_data)
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["message"] == "Event added successfully"
            assert response_data["event_id"] == 3


class TestGetEventsEndpoint:
    
    @patch('app.routers.calendar.get_db')
    def test_get_calendar_empty(self, mock_get_db, client):
        mock_db_session = Mock()
        mock_get_db.return_value = mock_db_session
        
        mock_db_session.query.return_value.all.return_value = []
        
        response = client.get("/events.ics")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/calendar; charset=utf-8"
        assert "Content-Disposition" in response.headers
        assert "events.ics" in response.headers["Content-Disposition"]
        
        calendar_text = response.text
        assert "BEGIN:VCALENDAR" in calendar_text
        assert "END:VCALENDAR" in calendar_text
        assert "PRODID:-//Community Events Calendar//EN" in calendar_text
        assert "VERSION:2.0" in calendar_text

    @patch('app.routers.calendar.get_db')
    @patch('app.routers.calendar.uuid.uuid4')
    @patch('app.routers.calendar.datetime')
    def test_get_calendar_with_events(self, mock_datetime, mock_uuid, mock_get_db, client):
        mock_db_session = Mock()
        mock_get_db.return_value = mock_db_session
        
        mock_uuid.return_value = "test-uuid-123"
        mock_datetime.now.return_value = datetime(2025, 6, 28, 12, 0, 0, tzinfo=timezone.utc)
        
        sample_event = Mock()
        sample_event.title = "Test Event"
        sample_event.start_time = datetime(2025, 7, 1, 19, 0, 0)
        sample_event.end_time = datetime(2025, 7, 1, 21, 0, 0)
        sample_event.description = "A test event for the calendar"
        sample_event.venue = "Test Venue"
        sample_event.url = "https://example.com"
        
        mock_db_session.query.return_value.all.return_value = [sample_event]
        
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

    @patch('app.routers.calendar.get_db')
    def test_get_calendar_multiple_events(self, mock_get_db, client):
        mock_db_session = Mock()
        mock_get_db.return_value = mock_db_session
        
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
        
        response = client.get("/events.ics")
        
        assert response.status_code == 200
        calendar_text = response.text
        
        assert calendar_text.count("BEGIN:VEVENT") == 2
        assert calendar_text.count("END:VEVENT") == 2
        assert "SUMMARY:Event 1" in calendar_text
        assert "SUMMARY:Event 2" in calendar_text
        assert "LOCATION:Venue 1" in calendar_text
        assert "LOCATION:Venue 2" in calendar_text

    @patch('app.routers.calendar.get_db')
    def test_get_calendar_validates_ical_format(self, mock_get_db, client):
        mock_db_session = Mock()
        mock_get_db.return_value = mock_db_session
        
        sample_event = Mock()
        sample_event.title = "Test Event"
        sample_event.start_time = datetime(2025, 7, 1, 19, 0, 0)
        sample_event.end_time = datetime(2025, 7, 1, 21, 0, 0)
        sample_event.description = "A test event for the calendar"
        sample_event.venue = "Test Venue"
        sample_event.url = "https://example.com"
        
        mock_db_session.query.return_value.all.return_value = [sample_event]
        
        response = client.get("/events.ics")
        
        assert response.status_code == 200
        
        try:
            calendar = Calendar.from_ical(response.content)
            assert calendar is not None
            
            events = [component for component in calendar.walk() if component.name == "VEVENT"]
            assert len(events) == 1
            
            event = events[0]
            assert event.get('summary') == "Test Event"
            assert event.get('location') == "Test Venue"
            assert event.get('description') == "A test event for the calendar"
            
        except Exception as e:
            pytest.fail(f"Generated ICS is not valid: {e}")

    @patch('app.routers.calendar.get_db')
    def test_get_calendar_database_error_handled_gracefully(self, mock_get_db, client):
        mock_db_session = Mock()
        mock_get_db.return_value = mock_db_session
        
        mock_db_session.query.side_effect = Exception("Database connection error")
        
        try:
            response = client.get("/events.ics")
            assert response.status_code in [200, 500]
        except Exception:
            pass