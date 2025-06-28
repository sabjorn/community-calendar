from fastapi import FastAPI

from .models import create_tables
from .routers import calendar

create_tables()

app = FastAPI()

app.include_router(calendar.router)
