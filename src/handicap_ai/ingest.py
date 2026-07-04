from __future__ import annotations

from collections.abc import Iterable

from handicap_ai.database import Database
from handicap_ai.models import NormalizedMatchBundle


def ingest_bundles(
    db: Database,
    bundles: Iterable[NormalizedMatchBundle],
) -> int:
    count = 0
    for bundle in bundles:
        for team in bundle.teams:
            db.upsert_team(team)
        db.upsert_match(bundle.match)
        for line in bundle.asian_handicaps:
            db.insert_asian_handicap(line)
        for line in bundle.totals:
            db.insert_total(line)
        for line in bundle.one_x_two:
            db.insert_one_x_two(line)
        count += 1
    return count
