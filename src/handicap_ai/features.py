from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

MarketKey = tuple[str | None, str | None]


@dataclass(frozen=True)
class MatchFeatures:
    open_handicap: float | None
    close_handicap: float | None
    handicap_delta: float | None
    open_total: float | None
    close_total: float | None
    total_delta: float | None
    home_water_delta: float | None
    away_water_delta: float | None
    over_water_delta: float | None
    under_water_delta: float | None
    closing_home_win_price: float | None
    closing_draw_price: float | None
    closing_away_win_price: float | None
    movement_patterns: tuple[str, ...]
    line_depth_score: float
    market_disagreement_score: float
    data_quality_score: float


def classify_movement(
    open_line: float | None,
    close_line: float | None,
    open_price: float | None,
    close_price: float | None,
) -> str:
    if open_line is None or close_line is None:
        return "line_missing"

    line_part = "line_stable"
    depth_delta = abs(close_line) - abs(open_line)
    if depth_delta >= 0.25:
        line_part = "line_up"
    elif depth_delta <= -0.25:
        line_part = "line_down"

    price_part = "price_missing"
    if open_price is not None and close_price is not None:
        price_delta = round(close_price - open_price, 4)
        if price_delta <= -0.03:
            price_part = "price_down"
        elif price_delta >= 0.03:
            price_part = "price_up"
        else:
            price_part = "price_stable"

    return f"{line_part}_{price_part}"


def build_match_features(
    asian_rows: Sequence[Any],
    total_rows: Sequence[Any],
    one_x_two_rows: Sequence[Any],
) -> MatchFeatures:
    asian_rows = tuple(asian_rows)
    total_rows = tuple(total_rows)
    one_x_two_rows = tuple(one_x_two_rows)

    open_asian, close_asian = _select_open_close_pair(asian_rows)
    open_total, close_total = _select_open_close_pair(total_rows)
    close_1x2 = _select_preferred_row(one_x_two_rows, "is_closing") or _last_row(
        one_x_two_rows
    )

    open_handicap = _float(open_asian, "line")
    close_handicap = _float(close_asian, "line")
    open_total_line = _float(open_total, "total")
    close_total_line = _float(close_total, "total")

    patterns = (
        classify_movement(
            open_handicap,
            close_handicap,
            _float(open_asian, "home_price"),
            _float(close_asian, "home_price"),
        ),
        classify_movement(
            open_total_line,
            close_total_line,
            _float(open_total, "over_price"),
            _float(close_total, "over_price"),
        ),
    )

    return MatchFeatures(
        open_handicap=open_handicap,
        close_handicap=close_handicap,
        handicap_delta=_delta(open_handicap, close_handicap),
        open_total=open_total_line,
        close_total=close_total_line,
        total_delta=_delta(open_total_line, close_total_line),
        home_water_delta=_delta(
            _float(open_asian, "home_price"), _float(close_asian, "home_price")
        ),
        away_water_delta=_delta(
            _float(open_asian, "away_price"), _float(close_asian, "away_price")
        ),
        over_water_delta=_delta(
            _float(open_total, "over_price"), _float(close_total, "over_price")
        ),
        under_water_delta=_delta(
            _float(open_total, "under_price"), _float(close_total, "under_price")
        ),
        closing_home_win_price=_float(close_1x2, "home_win_price"),
        closing_draw_price=_float(close_1x2, "draw_price"),
        closing_away_win_price=_float(close_1x2, "away_win_price"),
        movement_patterns=patterns,
        line_depth_score=abs(close_handicap or 0.0),
        market_disagreement_score=_market_disagreement(
            close_handicap,
            _float(close_1x2, "home_win_price"),
            _float(close_1x2, "draw_price"),
            _float(close_1x2, "away_win_price"),
        ),
        data_quality_score=_data_quality(
            open_asian, close_asian, open_total, close_total, close_1x2
        ),
    )


def _select_open_close_pair(rows: Sequence[Any]) -> tuple[Any | None, Any | None]:
    common_keys = {
        key
        for key in (_row_market_key(row) for row in rows)
        if key is not None
        and _has_flag(rows, key, "is_opening")
        and _has_flag(rows, key, "is_closing")
    }
    if common_keys:
        preferred_key = min(common_keys, key=_market_key_sort_key)
        return (
            _select_row_with_key(rows, "is_opening", preferred_key),
            _select_row_with_key(rows, "is_closing", preferred_key),
        )
    return (
        _select_preferred_row(rows, "is_opening"),
        _select_preferred_row(rows, "is_closing") or _last_row(rows),
    )


def _select_preferred_row(rows: Sequence[Any], flag: str) -> Any | None:
    candidates = [row for row in rows if _truthy(_row_get(row, flag))]
    if not candidates:
        return None
    if not any(_row_market_key(row) is not None for row in candidates):
        return candidates[0]
    return min(candidates, key=lambda row: _market_key_sort_key(_row_market_key(row)))


def _has_flag(rows: Sequence[Any], market_key: MarketKey, flag: str) -> bool:
    return any(
        _row_market_key(row) == market_key and _truthy(_row_get(row, flag))
        for row in rows
    )


def _select_row_with_key(
    rows: Sequence[Any], flag: str, market_key: MarketKey
) -> Any | None:
    return next(
        (
            row
            for row in rows
            if _row_market_key(row) == market_key and _truthy(_row_get(row, flag))
        ),
        None,
    )


def _row_market_key(row: Any) -> MarketKey | None:
    source = _normalized_identifier(_row_get(row, "source"))
    bookmaker = _normalized_identifier(_row_get(row, "bookmaker"))
    if source is None and bookmaker is None:
        return None
    return (source, bookmaker)


def _normalized_identifier(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def _market_key_sort_key(market_key: MarketKey | None) -> tuple[int, str, str]:
    if market_key is None:
        return (3, "", "")
    source, bookmaker = market_key
    market_name = bookmaker or source or ""
    if bookmaker == "b365":
        priority = 0
    elif bookmaker in {"market-average", "web-average"}:
        priority = 1
    else:
        priority = 2
    return (priority, market_name, source or "")


def _last_row(rows: Sequence[Any]) -> Any | None:
    return rows[-1] if rows else None


def _row_get(row: Any | None, key: str) -> object | None:
    if row is None:
        return None
    if isinstance(row, Mapping):
        return row.get(key)
    try:
        return row[key]
    except (IndexError, KeyError, TypeError):
        return None


def _truthy(value: object | None) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _float(row: Any | None, key: str) -> float | None:
    value = _row_get(row, key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(start: float | None, end: float | None) -> float | None:
    if start is None or end is None:
        return None
    return round(end - start, 4)


def _data_quality(
    open_asian: Any | None,
    close_asian: Any | None,
    open_total: Any | None,
    close_total: Any | None,
    close_1x2: Any | None,
) -> float:
    rows = (open_asian, close_asian, open_total, close_total, close_1x2)
    present = sum(1 for row in rows if row is not None)
    score = round(present / len(rows), 2)
    for open_row, close_row in (
        (open_asian, close_asian),
        (open_total, close_total),
    ):
        if (open_row is None) != (close_row is None):
            score = min(score, 0.49)
    return round(score, 2)


def _market_disagreement(
    close_handicap: float | None,
    home_win_price: float | None,
    draw_price: float | None,
    away_win_price: float | None,
) -> float:
    if close_handicap is None or close_handicap == 0:
        return 0.5
    probabilities = _normalized_implied_probabilities(
        home_win_price, draw_price, away_win_price
    )
    if probabilities is None:
        return 0.5

    home_probability, _, away_probability = probabilities
    favorite_probability = home_probability if close_handicap < 0 else away_probability
    required_probability = min(0.7, 0.48 + abs(close_handicap) * 0.06)
    return 0.2 if favorite_probability >= required_probability else 0.8


def _normalized_implied_probabilities(
    home_win_price: float | None,
    draw_price: float | None,
    away_win_price: float | None,
) -> tuple[float, float, float] | None:
    prices = (home_win_price, draw_price, away_win_price)
    if any(price is None or price <= 0 for price in prices):
        return None
    inverse_prices = tuple(1 / price for price in prices)
    total = sum(inverse_prices)
    if total <= 0:
        return None
    return tuple(inverse_price / total for inverse_price in inverse_prices)
