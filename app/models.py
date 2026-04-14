from pydantic import BaseModel
from typing import Optional
from datetime import date


class TournamentCreate(BaseModel):
    espn_tournament_id: str
    name: str
    stake_euros: float
    start_date: date
    end_date: date


class PicksCreate(BaseModel):
    player1_id: str
    player1_golfer1_id: str
    player1_golfer1_name: str
    player1_golfer2_id: str
    player1_golfer2_name: str
    player1_golfer3_id: str
    player1_golfer3_name: str
    player2_id: str
    player2_golfer1_id: str
    player2_golfer1_name: str
    player2_golfer2_id: str
    player2_golfer2_name: str
    player2_golfer3_id: str
    player2_golfer3_name: str


class BetResult(BaseModel):
    tournament_id: str
    betting_player_id: str
    golfer_espn_id: str
    golfer_name: str
    stroke_payout: float
    streak_payout: float
    top10_payout: float
    cut_penalty: float
    total_payout: float


class PlayerTotal(BaseModel):
    player_id: str
    player_name: str
    total: float
    results: list[BetResult]


class HoleScore(BaseModel):
    round_num: int
    hole_num: int
    score: int
    par: int
    score_to_par: int
