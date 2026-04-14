"""
ESPN unofficial JSON API client for golf data.

All 4 majors are covered under the /pga/ path.
Hole-by-hole data is nested in the scoreboard response — no separate endpoint needed.

Scoreboard URL: https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard
  - Add ?event={espn_tournament_id} for a specific tournament
  - Add ?dates=YYYYMMDD-YYYYMMDD to find a tournament by date range
"""

import httpx
from typing import Optional

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard"


async def fetch_scoreboard(espn_tournament_id: Optional[str] = None, dates: Optional[str] = None) -> dict:
    """Fetch the ESPN scoreboard. Returns the full response dict."""
    params = {}
    if espn_tournament_id:
        params["event"] = espn_tournament_id
    if dates:
        params["dates"] = dates

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(ESPN_BASE, params=params)
        resp.raise_for_status()
        return resp.json()


def _parse_score_to_par(display_value: str) -> int:
    """Convert ESPN score display ('E', '-2', '+3', '67') to int score-to-par."""
    v = display_value.strip()
    if v in ("E", "EVEN", ""):
        return 0
    try:
        return int(v)
    except ValueError:
        return 0


def parse_competitor(competitor: dict, espn_tournament_id: str) -> dict:
    """
    Parse a competitor blob from the ESPN scoreboard into our data model.

    Returns a dict with:
      - golfer_score: fields for golfer_scores table
      - hole_scores: list of dicts for hole_scores table
    """
    athlete = competitor.get("athlete", {})
    golfer_id = athlete.get("id", "") or competitor.get("id", "")
    golfer_name = athlete.get("displayName", "")

    # Position / status
    status = competitor.get("status", {})
    status_name = status.get("type", {}).get("name", "")
    position_display = competitor.get("displayOrder", "")

    # Try to get position as int
    position = None
    pos_val = competitor.get("order")
    if pos_val is not None:
        try:
            position = int(pos_val)
        except (ValueError, TypeError):
            pass

    # Total to par
    score_str = competitor.get("score", "E")
    total_to_par = _parse_score_to_par(str(score_str))

    made_cut = status_name not in ("STATUS_CUT", "STATUS_WD", "STATUS_DQ")
    is_complete = status_name == "STATUS_COMPLETE"

    # Parse hole-by-hole data from nested linescores
    hole_scores = []
    rounds = competitor.get("linescores", [])
    for rnd in rounds:
        round_num = rnd.get("period", 0)
        if not round_num:
            continue
        holes = rnd.get("linescores", [])
        for hole in holes:
            hole_num = hole.get("period", 0)
            if not hole_num:
                continue
            strokes = int(hole.get("value", 0))
            # Completed tournaments use scoreType.displayValue for to-par ("E", "-1", "+1")
            # Live/upcoming use displayValue directly
            score_type = hole.get("scoreType", {})
            stp_display = score_type.get("displayValue") or hole.get("displayValue", "E")
            score_to_par = _parse_score_to_par(stp_display)
            par = strokes - score_to_par if strokes else 0
            if strokes and par:
                hole_scores.append({
                    "tournament_id": None,  # filled by caller
                    "golfer_espn_id": golfer_id,
                    "round_num": round_num,
                    "hole_num": hole_num,
                    "score": strokes,
                    "par": par,
                    "score_to_par": score_to_par,
                })

    golfer_score = {
        "tournament_id": None,  # filled by caller
        "golfer_espn_id": golfer_id,
        "golfer_name": golfer_name,
        "position": position,
        "position_display": position_display,
        "total_to_par": total_to_par,
        "made_cut": made_cut,
        "is_complete": is_complete,
        "raw_espn_json": competitor,
    }

    return {"golfer_score": golfer_score, "hole_scores": hole_scores}


def extract_event(data: dict, espn_tournament_id: str) -> Optional[dict]:
    """Find the matching event in a scoreboard response."""
    for event in data.get("events", []):
        if str(event.get("id", "")) == str(espn_tournament_id):
            return event
    # If only one event, return it
    events = data.get("events", [])
    if len(events) == 1:
        return events[0]
    return None


def get_all_competitors(event: dict) -> list[dict]:
    """Extract all competitors from an event."""
    competitions = event.get("competitions", [])
    if not competitions:
        return []
    return competitions[0].get("competitors", [])


async def search_golfer(name: str, espn_tournament_id: Optional[str] = None) -> list[dict]:
    """
    Search for a golfer by name in a specific tournament's scoreboard,
    or the current live scoreboard if no tournament ID is given.
    Returns a list of matches: [{"id": ..., "name": ...}]
    """
    try:
        data = await fetch_scoreboard(espn_tournament_id=espn_tournament_id)
    except Exception:
        return []

    results = []
    name_lower = name.lower()
    seen = set()

    for event in data.get("events", []):
        for comp in get_all_competitors(event):
            athlete = comp.get("athlete", {})
            athlete_id = athlete.get("id", "") or comp.get("id", "")
            display_name = athlete.get("displayName", "")
            if athlete_id and athlete_id not in seen and name_lower in display_name.lower():
                results.append({"id": athlete_id, "name": display_name})
                seen.add(athlete_id)

    return results


async def fetch_tournament_info(espn_tournament_id: str) -> Optional[dict]:
    """Fetch basic info for a tournament by its ESPN ID."""
    try:
        data = await fetch_scoreboard(espn_tournament_id=espn_tournament_id)
        event = extract_event(data, espn_tournament_id)
        if not event:
            return None
        return {
            "name": event.get("name", ""),
            "short_name": event.get("shortName", ""),
            "start_date": event.get("date", ""),
        }
    except Exception:
        return None
