from fastapi import FastAPI

from .routers import calendar

app = FastAPI()

app.include_router(calendar.router)
