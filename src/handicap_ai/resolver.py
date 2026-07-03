from __future__ import annotations

import sqlite3

from rapidfuzz import fuzz

from handicap_ai.database import Database
from handicap_ai.names import normalize_team_name


class MatchResolver:
    def __init__(self, db: Database):
        self.db = db

    def resolve(self, home: str, away: str) -> sqlite3.Row:
        exact_matches = self.db.find_matches_by_names(home, away)
        if exact_matches:
            return exact_matches[0]

        normalized_home = normalize_team_name(home)
        normalized_away = normalize_team_name(away)
        fuzzy_matches: list[tuple[float, sqlite3.Row]] = []

        for match in self.db.execute("SELECT * FROM matches ORDER BY kickoff_time DESC"):
            home_score = fuzz.ratio(normalized_home, match["home_normalized"])
            away_score = fuzz.ratio(normalized_away, match["away_normalized"])
            score = min(home_score, away_score)
            if score >= 88:
                fuzzy_matches.append((score, match))

        if fuzzy_matches:
            fuzzy_matches.sort(key=lambda candidate: candidate[0], reverse=True)
            return fuzzy_matches[0][1]

        raise LookupError(f"No match found for {home} vs {away}")
