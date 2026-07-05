from handicap_ai.database import Database
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, import_world_cup_2026_seed


def test_world_cup_seed_imports_48_teams(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    summary = import_world_cup_2026_seed(db)

    teams = db.list_tournament_teams(FIFA_WORLD_CUP, "2026")
    assert summary.teams_imported == 48
    assert len(teams) == 48


def test_world_cup_seed_imports_group_k_and_l_teams(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    import_world_cup_2026_seed(db)

    teams = db.list_tournament_teams(FIFA_WORLD_CUP, "2026")
    grouped = {
        group_name: {
            row["team_name"] for row in teams if row["group_name"] == group_name
        }
        for group_name in ("K", "L")
    }
    assert grouped["K"] == {"Colombia", "Portugal", "DR Congo", "Uzbekistan"}
    assert grouped["L"] == {"England", "Croatia", "Ghana", "Panama"}


def test_world_cup_seed_import_is_idempotent(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    import_world_cup_2026_seed(db)
    import_world_cup_2026_seed(db)

    teams = db.list_tournament_teams(FIFA_WORLD_CUP, "2026")
    fixtures_count = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM tournament_fixtures
        WHERE tournament = ? AND season = ?
        """,
        (FIFA_WORLD_CUP, "2026"),
    )[0]["count"]
    aliases_count = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM tournament_team_aliases
        WHERE tournament = ? AND season = ?
        """,
        (FIFA_WORLD_CUP, "2026"),
    )[0]["count"]
    assert len(teams) == 48
    assert fixtures_count == 72
    assert aliases_count == 9


def test_world_cup_seed_imports_group_stage_fixtures(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    summary = import_world_cup_2026_seed(db)

    assert summary.fixtures_imported == 72
    england_ghana = db.find_tournament_fixtures(
        tournament=FIFA_WORLD_CUP,
        season="2026",
        home_team="England",
        away_team="Ghana",
    )
    portugal_uzbekistan = db.find_tournament_fixtures(
        tournament=FIFA_WORLD_CUP,
        season="2026",
        home_team="Portugal",
        away_team="Uzbekistan",
    )
    assert len(england_ghana) == 1
    assert england_ghana[0]["group_name"] == "L"
    assert len(portugal_uzbekistan) == 1
    assert portugal_uzbekistan[0]["group_name"] == "K"


def test_world_cup_seed_imports_aliases(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    summary = import_world_cup_2026_seed(db)

    assert summary.aliases_imported == 9
    assert (
        db.resolve_tournament_team(FIFA_WORLD_CUP, "2026", "Congo DR")["team_name"]
        == "DR Congo"
    )
    assert (
        db.resolve_tournament_team(
            FIFA_WORLD_CUP,
            "2026",
            "Democratic Republic of the Congo",
        )["team_name"]
        == "DR Congo"
    )
    assert (
        db.resolve_tournament_team(FIFA_WORLD_CUP, "2026", "USA")["team_name"]
        == "United States"
    )
    assert (
        db.resolve_tournament_team(FIFA_WORLD_CUP, "2026", "Korea Republic")[
            "team_name"
        ]
        == "South Korea"
    )
    assert (
        db.resolve_tournament_team(FIFA_WORLD_CUP, "2026", "Czechia")["team_name"]
        == "Czech Republic"
    )
