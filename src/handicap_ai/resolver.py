from __future__ import annotations

import sqlite3

from rapidfuzz import fuzz

from handicap_ai.database import Database
from handicap_ai.names import normalize_team_name


FUZZY_MATCH_THRESHOLD = 88
FUZZY_AMBIGUITY_MARGIN = 3


def _format_candidate_rows(matches: list[sqlite3.Row]) -> str:
    return "\n".join(
        (
            f"- competition={match['competition']}, "
            f"kickoff_time={match['kickoff_time']}, "
            f"home_team={match['home_team']}, "
            f"away_team={match['away_team']}"
        )
        for match in matches
    )


class MatchResolver:
    def __init__(self, db: Database):
        self.db = db

    def resolve(self, home: str, away: str) -> sqlite3.Row:
        exact_matches = self.db.find_matches_by_names(home, away)
        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(exact_matches) > 1:
            raise LookupError(
                f"Multiple matches found for {home} vs {away}:\n"
                f"{_format_candidate_rows(exact_matches)}"
            )

        normalized_home = normalize_team_name(home)
        normalized_away = normalize_team_name(away)
        fuzzy_matches: list[tuple[float, sqlite3.Row]] = []

        for match in self.db.execute("SELECT * FROM matches ORDER BY kickoff_time DESC"):
            home_score = fuzz.ratio(normalized_home, match["home_normalized"])
            away_score = fuzz.ratio(normalized_away, match["away_normalized"])
            score = min(home_score, away_score)
            if score >= FUZZY_MATCH_THRESHOLD:
                fuzzy_matches.append((score, match))

        if fuzzy_matches:
            fuzzy_matches.sort(key=lambda candidate: candidate[0], reverse=True)
            if len(fuzzy_matches) > 1:
                top_score = fuzzy_matches[0][0]
                second_score = fuzzy_matches[1][0]
                if top_score - second_score <= FUZZY_AMBIGUITY_MARGIN:
                    tied_matches = [
                        match
                        for score, match in fuzzy_matches
                        if top_score - score <= FUZZY_AMBIGUITY_MARGIN
                    ]
                    raise LookupError(
                        f"Multiple fuzzy matches found for {home} vs {away}:\n"
                        f"{_format_candidate_rows(tied_matches)}"
                    )
            return fuzzy_matches[0][1]

        raise LookupError(f"No match found for {home} vs {away}")
