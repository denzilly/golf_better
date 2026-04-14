from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routers import tournaments, picks, scores

app = FastAPI(title="Golf Betting Tracker")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(tournaments.router)
app.include_router(picks.router)
app.include_router(scores.router)
