from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MatchStatus(str, Enum):
    SCHEDULED = "scheduled"
    FINISHED = "finished"


class MarketType(str, Enum):
    ASIAN_HANDICAP = "asian_handicap"
    TOTALS = "totals"
    ONE_X_TWO = "1x2"


class Result1X2(str, Enum):
    HOME_WIN = "home_win"
    DRAW = "draw"
    AWAY_WIN = "away_win"


class HandicapCover(str, Enum):
    HOME_WIN = "home_cover"
    HOME_HALF_WIN = "home_half_win"
    PUSH = "push"
    HOME_HALF_LOSS = "home_half_loss"
    AWAY_WIN = "away_cover"


class TotalCover(str, Enum):
    OVER_WIN = "over"
    OVER_HALF_WIN = "over_half_win"
    PUSH = "push"
    UNDER_HALF_WIN = "under_half_win"
    UNDER_WIN = "under"


class Pick(str, Enum):
    HOME = "home"
    AWAY = "away"
    OVER = "over"
    UNDER = "under"
    DRAW = "draw"
    NO_BET = "no_bet"


@dataclass(frozen=True)
class TeamRecord:
    canonical_name: str
    country: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class MatchRecord:
    source_match_id: str
    home_team: str
    away_team: str
    competition: str
    season: str
    kickoff_time: datetime | None
    status: MatchStatus
    home_score: int | None = None
    away_score: int | None = None


@dataclass(frozen=True)
class OddsSnapshotRecord:
    source_match_id: str
    source: str
    bookmaker: str
    market_type: MarketType
    captured_at: datetime | None
    is_opening: bool
    is_closing: bool


@dataclass(frozen=True)
class AsianHandicapLineRecord:
    source_match_id: str
    source: str
    bookmaker: str
    is_opening: bool
    is_closing: bool
    line: float
    home_price: float | None
    away_price: float | None
    captured_at: datetime | None = None


@dataclass(frozen=True)
class TotalsLineRecord:
    source_match_id: str
    source: str
    bookmaker: str
    is_opening: bool
    is_closing: bool
    total: float
    over_price: float | None
    under_price: float | None
    captured_at: datetime | None = None


@dataclass(frozen=True)
class OneXTwoLineRecord:
    source_match_id: str
    source: str
    bookmaker: str
    is_opening: bool
    is_closing: bool
    home_win_price: float | None
    draw_price: float | None
    away_win_price: float | None
    captured_at: datetime | None = None


@dataclass(frozen=True)
class NormalizedMatchBundle:
    match: MatchRecord
    teams: tuple[TeamRecord, ...]
    asian_handicaps: tuple[AsianHandicapLineRecord, ...] = ()
    totals: tuple[TotalsLineRecord, ...] = ()
    one_x_two: tuple[OneXTwoLineRecord, ...] = ()
