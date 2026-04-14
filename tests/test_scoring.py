"""Unit tests for bet scoring logic."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.scoring import (
    stroke_payout,
    streak_payout,
    top10_payout,
    cut_penalty,
    _streak_cumulative_bonus,
)


# --- stroke_payout ---

def test_stroke_birdie_earns():
    assert stroke_payout(-2, 1.0) == 2.0

def test_stroke_bogey_loses():
    assert stroke_payout(3, 1.0) == -3.0

def test_stroke_even_zero():
    assert stroke_payout(0, 2.0) == 0.0

def test_stroke_stake_scaling():
    assert stroke_payout(-5, 2.0) == 10.0


# --- streak cumulative bonus ---

def test_streak_cumulative_below_2():
    assert _streak_cumulative_bonus(0) == 0.0
    assert _streak_cumulative_bonus(1) == 0.0

def test_streak_cumulative_at_2():
    assert _streak_cumulative_bonus(2) == 1.0  # 2^1 - 1

def test_streak_cumulative_at_3():
    assert _streak_cumulative_bonus(3) == 3.0  # 2^2 - 1

def test_streak_cumulative_at_4():
    assert _streak_cumulative_bonus(4) == 7.0  # 2^3 - 1


# --- streak_payout ---

def _hole(round_num, hole_num, score_to_par):
    return {"round_num": round_num, "hole_num": hole_num, "score_to_par": score_to_par}

def test_streak_no_consecutive():
    # Single birdie, no second in a row
    holes = [_hole(1, 1, -1), _hole(1, 2, 0), _hole(1, 3, -1)]
    assert streak_payout(holes, 1.0) == 0.0

def test_streak_two_birdies():
    # Two consecutive birdies → 1 bonus point
    holes = [_hole(1, 1, -1), _hole(1, 2, -1)]
    assert streak_payout(holes, 1.0) == 1.0

def test_streak_three_birdies():
    # Three consecutive birdies → cumulative 3 pts (delta 1 at h2, delta 2 at h3)
    holes = [_hole(1, 1, -1), _hole(1, 2, -1), _hole(1, 3, -1)]
    assert streak_payout(holes, 1.0) == 3.0

def test_streak_reset_on_par():
    # b-b-par-b-b = two separate streaks of 2 → 1 + 1 = 2 pts
    holes = [
        _hole(1, 1, -1), _hole(1, 2, -1),  # streak → 1pt
        _hole(1, 3, 0),                     # reset
        _hole(1, 4, -1), _hole(1, 5, -1),  # streak → 1pt
    ]
    assert streak_payout(holes, 1.0) == 2.0

def test_streak_eagle_counts_double():
    # Eagle (-2) = 2 units; one birdie before = streak hits 3 units = 3 pts
    holes = [_hole(1, 1, -1), _hole(1, 2, -2)]
    # birdie: streak 0→1 (no bonus), eagle: streak 1→3 (delta = cum(3)-cum(1) = 3-0 = 3)
    assert streak_payout(holes, 1.0) == 3.0

def test_streak_cross_round_boundary():
    # Birdie on last hole of round 1, birdie on first hole of round 2 → chain
    holes = [_hole(1, 18, -1), _hole(2, 1, -1)]
    assert streak_payout(holes, 1.0) == 1.0

def test_streak_stake_multiplied():
    holes = [_hole(1, 1, -1), _hole(1, 2, -1)]
    assert streak_payout(holes, 2.0) == 2.0

def test_streak_empty():
    assert streak_payout([], 1.0) == 0.0


# --- top10_payout ---

def test_top10_first_place():
    assert top10_payout(1, [1, 2, 3]) == 100.0

def test_top10_tenth_place():
    assert top10_payout(10, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) == 10.0

def test_top10_outside_top10():
    assert top10_payout(11, [1, 2, 11]) == 0.0

def test_top10_none_position():
    assert top10_payout(None, [1, 2]) == 0.0

def test_top10_tie_two_players():
    # T2 with 2 players: average prizes for pos 2 and 3 → (90+80)/2 = 85
    assert top10_payout(2, [1, 2, 2]) == 85.0

def test_top10_tie_three_players():
    # T2 with 3 players: average prizes for pos 2,3,4 → (90+80+70)/3 = 80
    assert top10_payout(2, [1, 2, 2, 2]) == 80.0

def test_top10_tie_at_tenth():
    # T10 with 2 players: only pos 10 is in prizes, pos 11 is not → 10/1 = 10
    assert top10_payout(10, [9, 10, 10]) == 10.0


# --- cut_penalty ---

def test_cut_penalty_missed():
    assert cut_penalty(False) == -25.0

def test_cut_penalty_made():
    assert cut_penalty(True) == 0.0


if __name__ == "__main__":
    import traceback
    tests = [
        test_stroke_birdie_earns, test_stroke_bogey_loses, test_stroke_even_zero,
        test_stroke_stake_scaling, test_streak_cumulative_below_2,
        test_streak_cumulative_at_2, test_streak_cumulative_at_3,
        test_streak_cumulative_at_4, test_streak_no_consecutive,
        test_streak_two_birdies, test_streak_three_birdies, test_streak_reset_on_par,
        test_streak_eagle_counts_double, test_streak_cross_round_boundary,
        test_streak_stake_multiplied, test_streak_empty,
        test_top10_first_place, test_top10_tenth_place, test_top10_outside_top10,
        test_top10_none_position, test_top10_tie_two_players,
        test_top10_tie_three_players, test_top10_tie_at_tenth,
        test_cut_penalty_missed, test_cut_penalty_made,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
