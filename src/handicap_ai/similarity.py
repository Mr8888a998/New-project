from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from handicap_ai.features import MatchFeatures


@dataclass(frozen=True)
class SimilarityCandidate:
    match_id: int
    features: MatchFeatures
    labels: Mapping[str, str]


@dataclass(frozen=True)
class SimilarityResult:
    match_id: int
    distance: float
    labels: Mapping[str, str]


def find_similar_matches(
    target: MatchFeatures,
    candidates: Sequence[SimilarityCandidate],
    limit: int = 20,
) -> list[SimilarityResult]:
    scored = [
        SimilarityResult(
            match_id=candidate.match_id,
            distance=_distance(target, candidate.features),
            labels=dict(candidate.labels),
        )
        for candidate in candidates
    ]
    scored.sort(key=lambda result: result.distance)
    return scored[:limit]


def _distance(left: MatchFeatures, right: MatchFeatures) -> float:
    fields = (
        ("open_handicap", 1.5),
        ("close_handicap", 2.0),
        ("handicap_delta", 1.0),
        ("open_total", 0.75),
        ("close_total", 0.75),
        ("total_delta", 0.75),
        ("home_water_delta", 0.5),
        ("over_water_delta", 0.5),
    )
    total = 0.0
    for field, weight in fields:
        left_value = getattr(left, field)
        right_value = getattr(right, field)
        if left_value is None or right_value is None:
            total += weight
        else:
            total += abs(left_value - right_value) * weight
    candidate_quality = min(max(right.data_quality_score, 0.0), 1.0)
    total += (1.0 - candidate_quality) * 5.0
    return round(total, 4)
