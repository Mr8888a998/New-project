from handicap_ai.database import Database


def test_database_upserts_tournament_teams_idempotently(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    db.upsert_tournament_team(
        tournament="fifa_world_cup",
        season="2026",
        group_name="L",
        team_name="England",
        country="England",
    )
    db.upsert_tournament_team(
        tournament="fifa_world_cup",
        season="2026",
        group_name="L",
        team_name="England",
        country="England",
    )

    rows = db.list_tournament_teams("fifa_world_cup", "2026")
    assert len(rows) == 1
    assert rows[0]["team_name"] == "England"
    assert rows[0]["group_name"] == "L"


def test_database_upserts_tournament_fixtures_and_source_links(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    fixture_id = db.upsert_tournament_fixture(
        tournament="fifa_world_cup",
        season="2026",
        group_name="L",
        home_team="England",
        away_team="Ghana",
        kickoff_time=None,
        status="scheduled",
    )
    second_id = db.upsert_tournament_fixture(
        tournament="fifa_world_cup",
        season="2026",
        group_name="L",
        home_team="England",
        away_team="Ghana",
        kickoff_time=None,
        status="scheduled",
    )
    db.upsert_fixture_source_link(
        fixture_id=fixture_id,
        source="betexplorer",
        html_path="tests/fixtures/betexplorer_match.html",
        url=None,
        status="available",
    )
    db.upsert_fixture_source_link(
        fixture_id=fixture_id,
        source="betexplorer",
        html_path="tests/fixtures/betexplorer_match_updated.html",
        url="https://example.com/match",
        status="refreshed",
    )

    assert second_id == fixture_id
    fixtures = db.find_tournament_fixtures(
        tournament="fifa_world_cup",
        season="2026",
        home_team="England",
        away_team="Ghana",
    )
    assert len(fixtures) == 1
    assert fixtures[0]["fixture_id"] == fixture_id
    links = db.list_fixture_source_links(fixture_id)
    assert len(links) == 1
    assert links[0]["source"] == "betexplorer"
    assert links[0]["html_path"] == "tests/fixtures/betexplorer_match_updated.html"
    assert links[0]["url"] == "https://example.com/match"
    assert links[0]["status"] == "refreshed"


def test_database_finds_tournament_fixture_by_reverse_team_order(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    fixture_id = db.upsert_tournament_fixture(
        tournament="fifa_world_cup",
        season="2026",
        group_name="L",
        home_team="England",
        away_team="Ghana",
        kickoff_time=None,
        status="scheduled",
    )

    fixtures = db.find_tournament_fixtures(
        tournament="fifa_world_cup",
        season="2026",
        home_team="Ghana",
        away_team="England",
    )

    assert len(fixtures) == 1
    assert fixtures[0]["fixture_id"] == fixture_id


def test_database_stores_team_aliases(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    db.upsert_tournament_team(
        tournament="fifa_world_cup",
        season="2026",
        group_name="K",
        team_name="DR Congo",
        country="DR Congo",
    )
    db.upsert_tournament_team_alias(
        tournament="fifa_world_cup",
        season="2026",
        team_name="DR Congo",
        alias="Congo DR",
    )

    row = db.resolve_tournament_team(
        tournament="fifa_world_cup",
        season="2026",
        name="Congo DR",
    )

    assert row is not None
    assert row["team_name"] == "DR Congo"
