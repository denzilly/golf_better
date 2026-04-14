from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Optional

from app.database import get_db
from app.config import settings
from app.services.refresh import refresh_tournament, refresh_all_active
from app.services.espn import search_golfer

router = APIRouter()


@router.post("/tournaments/{tournament_id}/refresh")
async def manual_refresh(tournament_id: str):
    t = get_db().table("tournaments").select("id").eq("id", tournament_id).single().execute().data
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    try:
        await refresh_tournament(tournament_id)
    except Exception as e:
        return RedirectResponse(f"/tournaments/{tournament_id}?error={str(e)}", status_code=303)
    return RedirectResponse(f"/tournaments/{tournament_id}", status_code=303)


@router.post("/internal/cron/refresh-all")
async def cron_refresh_all(authorization: Optional[str] = Header(None)):
    expected = f"Bearer {settings.cron_secret}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
    results = await refresh_all_active()
    return JSONResponse({"results": results})


@router.get("/api/golfer-search")
async def golfer_search(q: str = "", tournament_id: str = ""):
    if len(q) < 2:
        return JSONResponse([])
    results = await search_golfer(q, espn_tournament_id=tournament_id or None)
    return JSONResponse(results[:10])


@router.post("/api/players")
async def create_player(request: Request):
    """Create a betting player (used in setup)."""
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    db = get_db()
    try:
        result = db.table("betting_players").insert({"name": name}).execute()
        return JSONResponse(result.data[0])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/players")
async def list_players():
    db = get_db()
    players = db.table("betting_players").select("*").order("name").execute().data or []
    return JSONResponse(players)
