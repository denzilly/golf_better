"""
Bet payout calculation logic.

Rules:
1. Stroke to par:  -total_to_par * stake  (birdie = earn, bogey = lose)
2. Streak bonus:   consecutive birdies/eagles earn points × stake
                   eagle = 2 units, birdie = 1 unit
                   streak cumulative bonus: 2^(n-1) - 1  where n = units in streak
                   incremental bonus going from unit n-1 → n = 2^(n-2) for n>=2
                   streak resets on par or worse
                   streaks continue across round boundaries
3. Top-10 bonus:   flat euros (1st=100, 2nd=90, ..., 10th=10), tied positions averaged
4. Cut penalty:    -25 euros flat if golfer misses the cut (stake not applied)
"""

TOP10_PRIZES = {1: 100, 2: 90, 3: 80, 4: 70, 5: 60, 6: 50, 7: 40, 8: 30, 9: 20, 10: 10}


def stroke_payout(total_to_par: int, stake: float) -> float:
    """Earn money for under par, lose for over par."""
    return round(-total_to_par * stake, 2)


def _streak_cumulative_bonus(units: int) -> float:
    """
    Total bonus points accumulated at 'units' streak length.
    units < 2 → 0 pts
    units = 2 → 1 pt
    units = 3 → 3 pts
    units = 4 → 7 pts
    Formula: 2^(units-1) - 1
    """
    if units < 2:
        return 0.0
    return float(2 ** (units - 1) - 1)


def streak_payout(hole_scores: list[dict], stake: float) -> float:
    """
    Calculate streak bonus across all rounds (in round+hole order).

    hole_scores: list of dicts with keys round_num, hole_num, score_to_par
    Returns bonus euros earned from consecutive birdie/eagle streaks.
    """
    # Sort by round then hole to ensure correct order (including cross-round chains)
    sorted_holes = sorted(hole_scores, key=lambda h: (h["round_num"], h["hole_num"]))

    current_streak = 0  # units accumulated (birdie=1, eagle=2)
    total_bonus_points = 0.0

    for hole in sorted_holes:
        stp = hole["score_to_par"]
        if stp < 0:
            # Birdie or better: add |score_to_par| units
            units_gained = abs(stp)
            old_streak = current_streak
            current_streak += units_gained
            # Incremental bonus: difference in cumulative bonus
            bonus_delta = _streak_cumulative_bonus(current_streak) - _streak_cumulative_bonus(old_streak)
            total_bonus_points += bonus_delta
        else:
            # Par or worse: reset streak
            current_streak = 0

    return round(total_bonus_points * stake, 2)


def top10_payout(position: int | None, all_positions: list[int]) -> float:
    """
    Calculate flat top-10 finish bonus (not multiplied by stake).

    position: this golfer's numeric finishing position (1-based), None if not finished
    all_positions: list of ALL competitors' numeric positions (to detect ties)
    Returns flat euro amount.
    """
    if position is None or position > 10:
        return 0.0

    # Find all positions that are tied with this golfer
    tied_count = all_positions.count(position)
    if tied_count == 1:
        return float(TOP10_PRIZES.get(position, 0))

    # Ties: average the prizes for the affected positions
    tied_positions = sorted([p for p in all_positions if p == position])
    # Positions this tie covers (e.g. T3 with 3 players covers 3,4,5)
    covered = list(range(position, position + tied_count))
    prizes = [TOP10_PRIZES.get(p, 0) for p in covered if p <= 10]
    if not prizes:
        return 0.0
    return round(sum(prizes) / len(prizes), 2)


def cut_penalty(made_cut: bool) -> float:
    """Flat -25 euro penalty for missing the cut. Stake not applied."""
    return -25.0 if not made_cut else 0.0


def calculate_golfer_result(
    golfer_espn_id: str,
    golfer_name: str,
    tournament_id: str,
    betting_player_id: str,
    stake: float,
    total_to_par: int,
    made_cut: bool,
    position: int | None,
    hole_scores: list[dict],
    all_competitor_positions: list[int],
) -> dict:
    """
    Calculate all bet components for a single golfer and return a bet_results row.
    """
    sp = stroke_payout(total_to_par, stake)
    streak = streak_payout(hole_scores, stake)
    t10 = top10_payout(position, all_competitor_positions) if made_cut else 0.0
    cut = cut_penalty(made_cut)
    total = round(sp + streak + t10 + cut, 2)

    return {
        "tournament_id": tournament_id,
        "betting_player_id": betting_player_id,
        "golfer_espn_id": golfer_espn_id,
        "golfer_name": golfer_name,
        "stroke_payout": sp,
        "streak_payout": streak,
        "top10_payout": t10,
        "cut_penalty": cut,
        "total_payout": total,
    }
