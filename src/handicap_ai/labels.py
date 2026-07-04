from __future__ import annotations

from handicap_ai.models import HandicapCover, Result1X2, TotalCover


def label_to_recommendation_bucket(label: object) -> str:
    if isinstance(label, HandicapCover):
        if label in {HandicapCover.HOME_WIN, HandicapCover.HOME_HALF_WIN}:
            return "home_cover"
        if label in {HandicapCover.AWAY_WIN, HandicapCover.HOME_HALF_LOSS}:
            return "away_cover"
        return "push"

    if isinstance(label, TotalCover):
        if label in {TotalCover.OVER_WIN, TotalCover.OVER_HALF_WIN}:
            return "over"
        if label in {TotalCover.UNDER_WIN, TotalCover.UNDER_HALF_WIN}:
            return "under"
        return "push"

    if isinstance(label, Result1X2):
        return label.value

    raise TypeError(f"unsupported label type: {type(label)!r}")
