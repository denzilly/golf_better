"""
Tournament score refresh service.

Fetches the ESPN scoreboard for a tournament, upserts golfer_scores and hole_scores
for all picked golfers, then recalculates and upserts bet_results.
"""

import logging
from datetime import datetime, timezone

from app.database import get_db
from app.services import espn
from app.services.scoring import calculate_golfer_result

logger = logging.getLogger(__name__)


async def refresh_tournament(tournament_id: str) -> dict:
    """
    Full refresh cycle for one tournament.
    Returns a status dict with counts of updated rows.
    """
    db = get_db()

    # Load tournament
    t_row = db.table("tournaments").select("*").eq("id", tournament_id).single().execute()
    tournament = t_row.data
    if not tournament:
        raise ValueError(f"Tournament {tournament_id} not found")

    espn_id = tournament["espn_tournament_id"]
    stake = float(tournament["stake_euros"])

    # Load picks for this tournament
    picks_rows = db.table("picks").select("*, betting_players(id, name)").eq("tournament_id", tournament_id).execute()
    picks = picks_rows.data or []

    if not picks:
        logger.info(f"No picks for tournament {tournament_id}, skipping")
        return {"status": "no_picks"}

    # Collect all unique picked golfer IDs
    picked_golfer_ids = {p["golfer_espn_id"] for p in picks}

    # Fetch ESPN scoreboard for this tournament
    logger.info(f"Fetching ESPN scoreboard for event {espn_id}")
    try:
        data = await espn.fetch_scoreboard(espn_tournament_id=espn_id)
    except Exception as e:
        logger.error(f"ESPN fetch failed: {e}")
        raise

    event = espn.extract_event(data, espn_id)
    if not event:
        logger.warning(f"Event {espn_id} not found in ESPN response")
        return {"status": "event_not_found"}

    all_competitors = espn.get_all_competitors(event)

    # Parse and upsert golfer_scores + hole_scores for picked golfers
    all_positions = []
    golfer_data: dict[str, dict] = {}  # golfer_id → parsed data

    for comp in all_competitors:
        parsed = espn.parse_competitor(comp, espn_id)
        gs = parsed["golfer_score"]
        athlete_id = gs["golfer_espn_id"]

        # Collect all positions for top-10 tie calculation
        if gs["position"] is not None and gs["made_cut"]:
            all_positions.append(gs["position"])

        if athlete_id not in picked_golfer_ids:
            continue

        gs["tournament_id"] = tournament_id
        for hs in parsed["hole_scores"]:
            hs["tournament_id"] = tournament_id

        golfer_data[athlete_id] = {
            "golfer_score": gs,
            "hole_scores": parsed["hole_scores"],
        }

    # Upsert golfer_scores and hole_scores
    for gid, gdata in golfer_data.items():
        gs = gdata["golfer_score"]
        gs["updated_at"] = datetime.now(timezone.utc).isoformat()
        # Store raw JSON as string for jsonb
        gs_for_db = {k: v for k, v in gs.items() if k != "raw_espn_json"}
        gs_for_db["raw_espn_json"] = gs["raw_espn_json"]

        db.table("golfer_scores").upsert(
            gs_for_db,
            on_conflict="tournament_id,golfer_espn_id"
        ).execute()

        if gdata["hole_scores"]:
            db.table("hole_scores").upsert(
                gdata["hole_scores"],
                on_conflict="tournament_id,golfer_espn_id,round_num,hole_num"
            ).execute()

    # Recalculate bet_results for each betting player
    # Group picks by betting player
    player_picks: dict[str, list] = {}
    for pick in picks:
        pid = pick["betting_player_id"]
        player_picks.setdefault(pid, []).append(pick)

    results_to_upsert = []
    for player_id, player_pick_list in player_picks.items():
        for pick in player_pick_list:
            gid = pick["golfer_espn_id"]
            gdata = golfer_data.get(gid)
            if not gdata:
                # Golfer not found in ESPN response yet
                continue
            gs = gdata["golfer_score"]
            result = calculate_golfer_result(
                golfer_espn_id=gid,
                golfer_name=gs["golfer_name"],
                tournament_id=tournament_id,
                betting_player_id=player_id,
                stake=stake,
                total_to_par=gs["total_to_par"] or 0,
                made_cut=gs["made_cut"],
                position=gs["position"],
                hole_scores=gdata["hole_scores"],
                all_competitor_positions=all_positions,
            )
            result["updated_at"] = datetime.now(timezone.utc).isoformat()
            results_to_upsert.append(result)

    if results_to_upsert:
        db.table("bet_results").upsert(
            results_to_upsert,
            on_conflict="tournament_id,betting_player_id,golfer_espn_id"
        ).execute()

    # Update tournament last_refreshed_at and status
    event_status = event.get("status", {}).get("type", {}).get("name", "")
    new_status = tournament["status"]
    if event_status == "STATUS_FINAL":
        new_status = "complete"
    elif event_status in ("STATUS_IN_PROGRESS", "STATUS_ACTIVE"):
        new_status = "active"

    db.table("tournaments").update({
        "last_refreshed_at": datetime.now(timezone.utc).isoformat(),
        "status": new_status,
    }).eq("id", tournament_id).execute()

    logger.info(f"Refresh complete for tournament {tournament_id}")
    return {
        "status": "ok",
        "golfers_updated": len(golfer_data),
        "results_upserted": len(results_to_upsert),
    }


async def refresh_all_active() -> list[dict]:
    """Refresh all active tournaments. Called by the cron endpoint."""
    db = get_db()
    rows = db.table("tournaments").select("id").in_("status", ["active", "upcoming"]).execute()
    results = []
    for row in rows.data or []:
        try:
            r = await refresh_tournament(row["id"])
            results.append({"tournament_id": row["id"], **r})
        except Exception as e:
            logger.error(f"Failed to refresh {row['id']}: {e}")
            results.append({"tournament_id": row["id"], "status": "error", "error": str(e)})
    return results
