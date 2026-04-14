from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated

from app.database import get_db
from app.services import espn
from app.services.scoring import scoring_by_round

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    db = get_db()
    tournaments = db.table("tournaments").select("*").order("start_date", desc=True).execute().data or []
    players = db.table("betting_players").select("*").order("name").execute().data or []

    # For each tournament, get player totals from bet_results
    for t in tournaments:
        t["player_totals"] = {}
        for player in players:
            rows = db.table("bet_results").select("total_payout").eq("tournament_id", t["id"]).eq("betting_player_id", player["id"]).execute().data or []
            t["player_totals"][player["id"]] = round(sum(r["total_payout"] for r in rows), 2)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "tournaments": tournaments,
        "players": players,
    })


@router.get("/tournaments/new", response_class=HTMLResponse)
async def new_tournament_form(request: Request):
    players = get_db().table("betting_players").select("*").order("name").execute().data or []
    return templates.TemplateResponse("tournament_new.html", {
        "request": request,
        "players": players,
        "error": request.query_params.get("error"),
    })


@router.post("/tournaments")
async def create_tournament(
    request: Request,
    espn_tournament_id: Annotated[str, Form()],
    name: Annotated[str, Form()],
    stake_euros: Annotated[float, Form()],
    start_date: Annotated[str, Form()],
    end_date: Annotated[str, Form()],
):
    db = get_db()
    try:
        result = db.table("tournaments").insert({
            "espn_tournament_id": espn_tournament_id.strip(),
            "name": name.strip(),
            "stake_euros": stake_euros,
            "start_date": start_date,
            "end_date": end_date,
            "status": "upcoming",
        }).execute()
        tournament_id = result.data[0]["id"]
        return RedirectResponse(f"/tournaments/{tournament_id}/picks", status_code=303)
    except Exception as e:
        error = str(e)
        if "unique" in error.lower():
            error = "A tournament with that ESPN ID already exists."
        return RedirectResponse(f"/tournaments/new?error={error}", status_code=303)


@router.get("/tournaments/{tournament_id}", response_class=HTMLResponse)
async def tournament_detail(request: Request, tournament_id: str):
    db = get_db()

    t = db.table("tournaments").select("*").eq("id", tournament_id).single().execute().data
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")

    players = db.table("betting_players").select("*").order("name").execute().data or []

    # Load picks per player
    all_picks = db.table("picks").select("*").eq("tournament_id", tournament_id).execute().data or []

    # Load golfer scores for picked golfers
    picked_ids = list({p["golfer_espn_id"] for p in all_picks})
    golfer_scores = {}
    if picked_ids:
        gs_rows = db.table("golfer_scores").select("*").eq("tournament_id", tournament_id).in_("golfer_espn_id", picked_ids).execute().data or []
        golfer_scores = {g["golfer_espn_id"]: g for g in gs_rows}

    # Load hole scores for picked golfers (for expansion)
    hole_scores = {}
    if picked_ids:
        hs_rows = db.table("hole_scores").select("*").eq("tournament_id", tournament_id).in_("golfer_espn_id", picked_ids).order("round_num").order("hole_num").execute().data or []
        for hs in hs_rows:
            key = hs["golfer_espn_id"]
            hole_scores.setdefault(key, []).append(hs)

    # Load bet results per player
    bet_results = {}
    for player in players:
        rows = db.table("bet_results").select("*").eq("tournament_id", tournament_id).eq("betting_player_id", player["id"]).execute().data or []
        bet_results[player["id"]] = {r["golfer_espn_id"]: r for r in rows}

    # Build player view data
    player_data = []
    for player in players:
        player_picks = [p for p in all_picks if p["betting_player_id"] == player["id"]]
        results = bet_results.get(player["id"], {})
        total = round(sum(r["total_payout"] for r in results.values()), 2)
        golfers = []
        for pick in player_picks:
            gid = pick["golfer_espn_id"]
            holes = hole_scores.get(gid, [])
            stake = float(t["stake_euros"])
            round_breakdown = scoring_by_round(holes, stake)

            # Build scorecard: pars by hole, and hole data indexed by [round][hole]
            pars: dict[int, int] = {}
            rounds_map: dict[int, dict[int, dict]] = {}
            for hole in holes:
                h, r = hole["hole_num"], hole["round_num"]
                pars[h] = hole["par"]
                rounds_map.setdefault(r, {})[h] = hole
            hole_nums = sorted(pars.keys())

            golfers.append({
                "espn_id": gid,
                "name": pick["golfer_name"],
                "score": golfer_scores.get(gid, {}),
                "result": results.get(gid, {}),
                "round_breakdown": round_breakdown,
                "scorecard": {
                    "hole_nums": hole_nums,
                    "pars": pars,
                    "par_total": sum(pars.values()),
                    "rounds": rounds_map,
                    "round_nums": sorted(rounds_map.keys()),
                },
            })
        player_data.append({
            "player": player,
            "total": total,
            "golfers": golfers,
        })

    return templates.TemplateResponse("tournament.html", {
        "request": request,
        "tournament": t,
        "player_data": player_data,
        "has_picks": len(all_picks) > 0,
    })
