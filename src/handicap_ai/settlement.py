from __future__ import annotations

import math

from handicap_ai.models import HandicapCover, Result1X2, TotalCover


def settle_one_x_two(home_score: int, away_score: int) -> Result1X2:
    if home_score > away_score:
        return Result1X2.HOME_WIN
    if home_score < away_score:
        return Result1X2.AWAY_WIN
    return Result1X2.DRAW


def settle_handicap(home_score: int, away_score: int, home_line: float) -> HandicapCover:
    margin = home_score - away_score
    legs = _split_quarter_line(home_line)
    score = sum(_single_handicap_result(margin, leg) for leg in legs) / len(legs)

    if math.isclose(score, 1.0):
        return HandicapCover.HOME_WIN
    if math.isclose(score, 0.5):
        return HandicapCover.HOME_HALF_WIN
    if math.isclose(score, 0.0):
        return HandicapCover.PUSH
    if math.isclose(score, -0.5):
        return HandicapCover.HOME_HALF_LOSS
    return HandicapCover.AWAY_WIN


def settle_total(home_score: int, away_score: int, total_line: float) -> TotalCover:
    goals = home_score + away_score
    legs = _split_quarter_line(total_line)
    score = sum(_single_total_result(goals, leg) for leg in legs) / len(legs)

    if math.isclose(score, 1.0):
        return TotalCover.OVER_WIN
    if math.isclose(score, 0.5):
        return TotalCover.OVER_HALF_WIN
    if math.isclose(score, 0.0):
        return TotalCover.PUSH
    if math.isclose(score, -0.5):
        return TotalCover.UNDER_HALF_WIN
    return TotalCover.UNDER_WIN


def _split_quarter_line(line: float) -> tuple[float, ...]:
    nearest_half = round(line * 2) / 2
    if math.isclose(line, nearest_half):
        return (nearest_half,)

    lower = math.floor(line * 2) / 2
    upper = lower + 0.5
    return (lower, upper)


def _single_handicap_result(margin: int, home_line: float) -> float:
    adjusted = margin + home_line
    if adjusted > 0:
        return 1.0
    if adjusted < 0:
        return -1.0
    return 0.0


def _single_total_result(goals: int, total_line: float) -> float:
    adjusted = goals - total_line
    if adjusted > 0:
        return 1.0
    if adjusted < 0:
        return -1.0
    return 0.0
