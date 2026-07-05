from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from handicap_ai.database import Database


FIFA_WORLD_CUP = "fifa_world_cup"
SEASON_2026 = "2026"


@dataclass(frozen=True)
class SeedTeam:
    group_name: str
    team_name: str
    country: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class SeedFixture:
    group_name: str
    home_team: str
    away_team: str
    kickoff_time: str | None = None
    status: str = "scheduled"


@dataclass(frozen=True)
class WorldCupSeedSummary:
    teams_imported: int
    fixtures_imported: int
    aliases_imported: int


WORLD_CUP_2026_GROUPS: tuple[SeedTeam, ...] = (
    SeedTeam("A", "Mexico"),
    SeedTeam("A", "South Africa"),
    SeedTeam("A", "South Korea", aliases=("Korea Republic", "Korea Rep")),
    SeedTeam("A", "Czech Republic", aliases=("Czechia",)),
    SeedTeam("B", "Canada"),
    SeedTeam("B", "Bosnia and Herzegovina"),
    SeedTeam("B", "Qatar"),
    SeedTeam("B", "Switzerland"),
    SeedTeam("C", "Brazil"),
    SeedTeam("C", "Morocco"),
    SeedTeam("C", "Haiti"),
    SeedTeam("C", "Scotland"),
    SeedTeam("D", "United States", aliases=("USA", "USMNT")),
    SeedTeam("D", "Paraguay"),
    SeedTeam("D", "Australia"),
    SeedTeam("D", "Turkey"),
    SeedTeam("E", "Germany"),
    SeedTeam("E", "Curacao"),
    SeedTeam("E", "Ivory Coast", aliases=("Cote d'Ivoire", "Cote d Ivoire")),
    SeedTeam("E", "Ecuador"),
    SeedTeam("F", "Netherlands"),
    SeedTeam("F", "Japan"),
    SeedTeam("F", "Sweden"),
    SeedTeam("F", "Tunisia"),
    SeedTeam("G", "Belgium"),
    SeedTeam("G", "Egypt"),
    SeedTeam("G", "Iran"),
    SeedTeam("G", "New Zealand"),
    SeedTeam("H", "Spain"),
    SeedTeam("H", "Cape Verde"),
    SeedTeam("H", "Saudi Arabia"),
    SeedTeam("H", "Uruguay"),
    SeedTeam("I", "France"),
    SeedTeam("I", "Senegal"),
    SeedTeam("I", "Iraq"),
    SeedTeam("I", "Norway"),
    SeedTeam("J", "Argentina"),
    SeedTeam("J", "Algeria"),
    SeedTeam("J", "Austria"),
    SeedTeam("J", "Jordan"),
    SeedTeam("K", "Colombia"),
    SeedTeam("K", "Portugal"),
    SeedTeam("K", "DR Congo", aliases=("Congo DR", "Democratic Republic of the Congo")),
    SeedTeam("K", "Uzbekistan"),
    SeedTeam("L", "England"),
    SeedTeam("L", "Croatia"),
    SeedTeam("L", "Ghana"),
    SeedTeam("L", "Panama"),
)


def world_cup_2026_fixtures() -> tuple[SeedFixture, ...]:
    fixtures: list[SeedFixture] = []
    for group_name in "ABCDEFGHIJKL":
        group_teams = [
            team.team_name
            for team in WORLD_CUP_2026_GROUPS
            if team.group_name == group_name
        ]
        fixtures.extend(
            SeedFixture(
                group_name=group_name,
                home_team=home_team,
                away_team=away_team,
            )
            for home_team, away_team in combinations(group_teams, 2)
        )
    return tuple(fixtures)


def import_world_cup_2026_seed(
    db: Database,
    *,
    overwrite_existing: bool = True,
) -> WorldCupSeedSummary:
    alias_count = 0
    fixture_count = 0
    fixtures = world_cup_2026_fixtures()

    for team in WORLD_CUP_2026_GROUPS:
        db.upsert_tournament_team(
            tournament=FIFA_WORLD_CUP,
            season=SEASON_2026,
            group_name=team.group_name,
            team_name=team.team_name,
            country=team.country or team.team_name,
        )
        for alias in team.aliases:
            db.upsert_tournament_team_alias(
                tournament=FIFA_WORLD_CUP,
                season=SEASON_2026,
                team_name=team.team_name,
                alias=alias,
            )
            alias_count += 1

    for fixture in fixtures:
        if not overwrite_existing and db.find_tournament_fixtures(
            FIFA_WORLD_CUP,
            SEASON_2026,
            fixture.home_team,
            fixture.away_team,
        ):
            continue
        db.upsert_tournament_fixture(
            tournament=FIFA_WORLD_CUP,
            season=SEASON_2026,
            group_name=fixture.group_name,
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            kickoff_time=fixture.kickoff_time,
            status=fixture.status,
        )
        fixture_count += 1

    return WorldCupSeedSummary(
        teams_imported=len(WORLD_CUP_2026_GROUPS),
        fixtures_imported=fixture_count,
        aliases_imported=alias_count,
    )
