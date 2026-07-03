from __future__ import annotations

from contextlib import closing
import sqlite3
from pathlib import Path
from typing import Any, Sequence

from handicap_ai.models import (
    AsianHandicapLineRecord,
    MatchRecord,
    OneXTwoLineRecord,
    TeamRecord,
    TotalsLineRecord,
)
from handicap_ai.names import normalize_team_name


SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
  team_id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_name TEXT NOT NULL,
  normalized_name TEXT NOT NULL UNIQUE,
  country TEXT
);

CREATE TABLE IF NOT EXISTS matches (
  match_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_match_id TEXT NOT NULL UNIQUE,
  home_team TEXT NOT NULL,
  away_team TEXT NOT NULL,
  home_normalized TEXT NOT NULL,
  away_normalized TEXT NOT NULL,
  competition TEXT NOT NULL,
  season TEXT NOT NULL,
  kickoff_time TEXT,
  status TEXT NOT NULL,
  home_score INTEGER,
  away_score INTEGER
);

CREATE TABLE IF NOT EXISTS asian_handicap_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  bookmaker TEXT NOT NULL,
  is_opening INTEGER NOT NULL,
  is_closing INTEGER NOT NULL,
  line REAL NOT NULL,
  home_price REAL,
  away_price REAL,
  captured_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(match_id) REFERENCES matches(match_id)
);

CREATE TABLE IF NOT EXISTS totals_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  bookmaker TEXT NOT NULL,
  is_opening INTEGER NOT NULL,
  is_closing INTEGER NOT NULL,
  total REAL NOT NULL,
  over_price REAL,
  under_price REAL,
  captured_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(match_id) REFERENCES matches(match_id)
);

CREATE TABLE IF NOT EXISTS one_x_two_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  bookmaker TEXT NOT NULL,
  is_opening INTEGER NOT NULL,
  is_closing INTEGER NOT NULL,
  home_win_price REAL,
  draw_price REAL,
  away_win_price REAL,
  captured_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(match_id) REFERENCES matches(match_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_normalized_names
ON matches(home_normalized, away_normalized, kickoff_time);

CREATE INDEX IF NOT EXISTS idx_asian_handicap_lines_match
ON asian_handicap_lines(match_id, is_opening, captured_at, id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_asian_handicap_lines_identity
ON asian_handicap_lines(
  match_id,
  source,
  bookmaker,
  is_opening,
  is_closing,
  line,
  COALESCE(captured_at, '')
);

CREATE INDEX IF NOT EXISTS idx_totals_lines_match
ON totals_lines(match_id, is_opening, captured_at, id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_totals_lines_identity
ON totals_lines(
  match_id,
  source,
  bookmaker,
  is_opening,
  is_closing,
  total,
  COALESCE(captured_at, '')
);

CREATE INDEX IF NOT EXISTS idx_one_x_two_lines_match
ON one_x_two_lines(match_id, is_opening, captured_at, id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_one_x_two_lines_identity
ON one_x_two_lines(
  match_id,
  source,
  bookmaker,
  is_opening,
  is_closing,
  COALESCE(captured_at, '')
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def migrate(self) -> None:
        with closing(self.connect()) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def execute(
        self,
        sql: str,
        parameters: Sequence[Any] = (),
    ) -> list[sqlite3.Row]:
        with closing(self.connect()) as conn:
            return list(conn.execute(sql, parameters))

    def upsert_team(self, team: TeamRecord) -> None:
        with closing(self.connect()) as conn:
            conn.execute(
                """
                INSERT INTO teams (canonical_name, normalized_name, country)
                VALUES (?, ?, ?)
                ON CONFLICT(normalized_name) DO UPDATE SET
                  canonical_name = excluded.canonical_name,
                  country = COALESCE(excluded.country, teams.country)
                """,
                (
                    team.canonical_name,
                    normalize_team_name(team.canonical_name),
                    team.country,
                ),
            )
            conn.commit()

    def upsert_match(self, match: MatchRecord) -> int:
        kickoff_time = match.kickoff_time.isoformat() if match.kickoff_time else None
        with closing(self.connect()) as conn:
            conn.execute(
                """
                INSERT INTO matches (
                  source_match_id,
                  home_team,
                  away_team,
                  home_normalized,
                  away_normalized,
                  competition,
                  season,
                  kickoff_time,
                  status,
                  home_score,
                  away_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_match_id) DO UPDATE SET
                  home_team = excluded.home_team,
                  away_team = excluded.away_team,
                  home_normalized = excluded.home_normalized,
                  away_normalized = excluded.away_normalized,
                  competition = excluded.competition,
                  season = excluded.season,
                  kickoff_time = excluded.kickoff_time,
                  status = excluded.status,
                  home_score = excluded.home_score,
                  away_score = excluded.away_score
                """,
                (
                    match.source_match_id,
                    match.home_team,
                    match.away_team,
                    normalize_team_name(match.home_team),
                    normalize_team_name(match.away_team),
                    match.competition,
                    match.season,
                    kickoff_time,
                    match.status.value,
                    match.home_score,
                    match.away_score,
                ),
            )
            row = conn.execute(
                "SELECT match_id FROM matches WHERE source_match_id = ?",
                (match.source_match_id,),
            ).fetchone()
            conn.commit()
            return int(row["match_id"])

    def insert_asian_handicap(self, line: AsianHandicapLineRecord) -> None:
        captured_at = line.captured_at.isoformat() if line.captured_at else ""
        with closing(self.connect()) as conn:
            match = conn.execute(
                "SELECT match_id FROM matches WHERE source_match_id = ?",
                (line.source_match_id,),
            ).fetchone()
            if match is None:
                raise ValueError(
                    f"match not found for source_match_id {line.source_match_id!r}"
                )

            conn.execute(
                """
                INSERT INTO asian_handicap_lines (
                  match_id,
                  source,
                  bookmaker,
                  is_opening,
                  is_closing,
                  line,
                  home_price,
                  away_price,
                  captured_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO UPDATE SET
                  home_price = excluded.home_price,
                  away_price = excluded.away_price
                """,
                (
                    match["match_id"],
                    line.source,
                    line.bookmaker,
                    int(line.is_opening),
                    int(line.is_closing),
                    line.line,
                    line.home_price,
                    line.away_price,
                    captured_at,
                ),
            )
            conn.commit()

    def insert_total(self, line: TotalsLineRecord) -> None:
        captured_at = line.captured_at.isoformat() if line.captured_at else ""
        with closing(self.connect()) as conn:
            match = conn.execute(
                "SELECT match_id FROM matches WHERE source_match_id = ?",
                (line.source_match_id,),
            ).fetchone()
            if match is None:
                raise ValueError(
                    f"match not found for source_match_id {line.source_match_id!r}"
                )

            conn.execute(
                """
                INSERT INTO totals_lines (
                  match_id,
                  source,
                  bookmaker,
                  is_opening,
                  is_closing,
                  total,
                  over_price,
                  under_price,
                  captured_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO UPDATE SET
                  over_price = excluded.over_price,
                  under_price = excluded.under_price
                """,
                (
                    match["match_id"],
                    line.source,
                    line.bookmaker,
                    int(line.is_opening),
                    int(line.is_closing),
                    line.total,
                    line.over_price,
                    line.under_price,
                    captured_at,
                ),
            )
            conn.commit()

    def insert_one_x_two(self, line: OneXTwoLineRecord) -> None:
        captured_at = line.captured_at.isoformat() if line.captured_at else ""
        with closing(self.connect()) as conn:
            match = conn.execute(
                "SELECT match_id FROM matches WHERE source_match_id = ?",
                (line.source_match_id,),
            ).fetchone()
            if match is None:
                raise ValueError(
                    f"match not found for source_match_id {line.source_match_id!r}"
                )

            conn.execute(
                """
                INSERT INTO one_x_two_lines (
                  match_id,
                  source,
                  bookmaker,
                  is_opening,
                  is_closing,
                  home_win_price,
                  draw_price,
                  away_win_price,
                  captured_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO UPDATE SET
                  home_win_price = excluded.home_win_price,
                  draw_price = excluded.draw_price,
                  away_win_price = excluded.away_win_price
                """,
                (
                    match["match_id"],
                    line.source,
                    line.bookmaker,
                    int(line.is_opening),
                    int(line.is_closing),
                    line.home_win_price,
                    line.draw_price,
                    line.away_win_price,
                    captured_at,
                ),
            )
            conn.commit()

    def find_matches_by_names(self, home_team: str, away_team: str) -> list[sqlite3.Row]:
        return self.execute(
            """
            SELECT *
            FROM matches
            WHERE home_normalized = ? AND away_normalized = ?
            ORDER BY kickoff_time DESC, match_id DESC
            """,
            (normalize_team_name(home_team), normalize_team_name(away_team)),
        )

    def get_asian_handicaps(self, match_id: int) -> list[sqlite3.Row]:
        return self.execute(
            """
            SELECT *
            FROM asian_handicap_lines
            WHERE match_id = ?
            ORDER BY is_opening DESC, COALESCE(captured_at, '') ASC, id ASC
            """,
            (match_id,),
        )

    def get_totals(self, match_id: int) -> list[sqlite3.Row]:
        return self.execute(
            """
            SELECT *
            FROM totals_lines
            WHERE match_id = ?
            ORDER BY is_opening DESC, COALESCE(captured_at, '') ASC, id ASC
            """,
            (match_id,),
        )

    def get_one_x_two(self, match_id: int) -> list[sqlite3.Row]:
        return self.execute(
            """
            SELECT *
            FROM one_x_two_lines
            WHERE match_id = ?
            ORDER BY is_opening DESC, COALESCE(captured_at, '') ASC, id ASC
            """,
            (match_id,),
        )
