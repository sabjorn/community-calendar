from fastapi import FastAPI

from .config import settings
from .models import create_tables
from .routers import calendar

create_tables()

app = FastAPI(
    title=settings.app_title,
    description=settings.app_description,
)

app.include_router(calendar.router)
