from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated

from app.database import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/tournaments/{tournament_id}/picks", response_class=HTMLResponse)
async def picks_form(request: Request, tournament_id: str):
    db = get_db()
    t = db.table("tournaments").select("*").eq("id", tournament_id).single().execute().data
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")

    players = db.table("betting_players").select("*").order("name").execute().data or []

    # Load existing picks
    existing = db.table("picks").select("*").eq("tournament_id", tournament_id).execute().data or []
    existing_by_player: dict[str, list] = {}
    for pick in existing:
        existing_by_player.setdefault(pick["betting_player_id"], []).append(pick)

    return templates.TemplateResponse("picks.html", {
        "request": request,
        "tournament": t,
        "players": players,
        "existing_by_player": existing_by_player,
        "error": request.query_params.get("error"),
    })


@router.post("/tournaments/{tournament_id}/picks")
async def save_picks(
    request: Request,
    tournament_id: str,
):
    db = get_db()
    form = await request.form()

    t = db.table("tournaments").select("id").eq("id", tournament_id).single().execute().data
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")

    players = db.table("betting_players").select("*").order("name").execute().data or []

    # Parse picks from form: player_{player_id}_golfer_{1,2,3}_id and _name
    picks_to_insert = []
    for player in players:
        pid = player["id"]
        for i in range(1, 4):
            gid = form.get(f"player_{pid}_golfer_{i}_id", "").strip()
            gname = form.get(f"player_{pid}_golfer_{i}_name", "").strip()
            if gid and gname:
                picks_to_insert.append({
                    "tournament_id": tournament_id,
                    "betting_player_id": pid,
                    "golfer_espn_id": gid,
                    "golfer_name": gname,
                })

    if not picks_to_insert:
        return RedirectResponse(
            f"/tournaments/{tournament_id}/picks?error=No+valid+picks+entered",
            status_code=303
        )

    # Delete existing picks and re-insert
    db.table("picks").delete().eq("tournament_id", tournament_id).execute()
    db.table("picks").insert(picks_to_insert).execute()

    return RedirectResponse(f"/tournaments/{tournament_id}", status_code=303)
