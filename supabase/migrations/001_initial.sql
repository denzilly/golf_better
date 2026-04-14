-- Golf Betting Tracker Schema

create extension if not exists "pgcrypto";

-- Betting players (the two people who bet against each other)
create table if not exists betting_players (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    created_at timestamptz default now()
);

-- Tournaments
create table if not exists tournaments (
    id uuid primary key default gen_random_uuid(),
    espn_tournament_id text not null unique,
    name text not null,
    stake_euros numeric(5,2) not null,
    status text not null default 'upcoming' check (status in ('upcoming', 'active', 'complete')),
    start_date date not null,
    end_date date not null,
    last_refreshed_at timestamptz,
    created_at timestamptz default now()
);

-- Picks: each betting player selects 3 golfers per tournament
create table if not exists picks (
    id uuid primary key default gen_random_uuid(),
    tournament_id uuid not null references tournaments(id) on delete cascade,
    betting_player_id uuid not null references betting_players(id) on delete cascade,
    golfer_espn_id text not null,
    golfer_name text not null,
    created_at timestamptz default now(),
    unique(tournament_id, betting_player_id, golfer_espn_id)
);

-- Golfer tournament scores (one row per golfer per tournament, updated on refresh)
create table if not exists golfer_scores (
    id uuid primary key default gen_random_uuid(),
    tournament_id uuid not null references tournaments(id) on delete cascade,
    golfer_espn_id text not null,
    golfer_name text not null,
    position int,
    position_display text,
    total_to_par int,
    made_cut boolean default true,
    is_complete boolean default false,
    raw_espn_json jsonb,
    updated_at timestamptz default now(),
    unique(tournament_id, golfer_espn_id)
);

-- Hole-by-hole scores for picked golfers
create table if not exists hole_scores (
    id uuid primary key default gen_random_uuid(),
    tournament_id uuid not null references tournaments(id) on delete cascade,
    golfer_espn_id text not null,
    round_num int not null check (round_num between 1 and 4),
    hole_num int not null check (hole_num between 1 and 18),
    score int not null,
    par int not null,
    score_to_par int not null,
    unique(tournament_id, golfer_espn_id, round_num, hole_num)
);

-- Computed bet results cache (rewritten on each refresh)
create table if not exists bet_results (
    id uuid primary key default gen_random_uuid(),
    tournament_id uuid not null references tournaments(id) on delete cascade,
    betting_player_id uuid not null references betting_players(id) on delete cascade,
    golfer_espn_id text not null,
    golfer_name text not null,
    stroke_payout numeric(8,2) not null default 0,
    streak_payout numeric(8,2) not null default 0,
    top10_payout numeric(8,2) not null default 0,
    cut_penalty numeric(8,2) not null default 0,
    total_payout numeric(8,2) not null default 0,
    updated_at timestamptz default now(),
    unique(tournament_id, betting_player_id, golfer_espn_id)
);

-- Indexes for common queries
create index if not exists idx_picks_tournament on picks(tournament_id);
create index if not exists idx_hole_scores_golfer on hole_scores(tournament_id, golfer_espn_id);
create index if not exists idx_bet_results_tournament on bet_results(tournament_id);
create index if not exists idx_golfer_scores_tournament on golfer_scores(tournament_id);
