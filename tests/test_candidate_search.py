from handicap_ai.candidate_search import CandidateStatus, find_world_cup_candidates
from handicap_ai.database import Database
from handicap_ai.world_cup_seed import import_world_cup_2026_seed


def seeded_db(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    return db


def test_candidate_search_finds_group_l_fixture(tmp_path):
    db = seeded_db(tmp_path)

    result = find_world_cup_candidates(db, home_team="England", away_team="Ghana")

    assert result.status is CandidateStatus.NEEDS_HTML
    assert result.candidates[0].home_team == "England"
    assert result.candidates[0].away_team == "Ghana"
    assert result.candidates[0].group_name == "L"


def test_candidate_search_resolves_aliases(tmp_path):
    db = seeded_db(tmp_path)

    result = find_world_cup_candidates(db, home_team="Portugal", away_team="Congo DR")

    assert result.status is CandidateStatus.NEEDS_HTML
    assert result.candidates[0].home_team == "Portugal"
    assert result.candidates[0].away_team == "DR Congo"
    assert result.candidates[0].group_name == "K"


def test_candidate_search_reports_invalid_team(tmp_path):
    db = seeded_db(tmp_path)

    result = find_world_cup_candidates(db, home_team="Atlantis", away_team="Ghana")

    assert result.status is CandidateStatus.INVALID_TEAM
    assert result.candidates == ()
    assert "Unknown team: Atlantis" in result.warnings


def test_candidate_search_reports_all_invalid_teams(tmp_path):
    db = seeded_db(tmp_path)

    result = find_world_cup_candidates(db, home_team="Atlantis", away_team="El Dorado")

    assert result.status is CandidateStatus.INVALID_TEAM
    assert result.candidates == ()
    assert result.warnings == ("Unknown team: Atlantis", "Unknown team: El Dorado")


def test_candidate_search_reports_not_in_group_stage(tmp_path):
    db = seeded_db(tmp_path)

    result = find_world_cup_candidates(db, home_team="England", away_team="Portugal")

    assert result.status is CandidateStatus.NOT_IN_GROUP_STAGE
    assert result.candidates == ()
    assert "Both teams are seeded, but no group-stage fixture was found" in result.warnings


def test_candidate_search_marks_ready_when_source_link_exists(tmp_path):
    db = seeded_db(tmp_path)
    fixture = db.find_tournament_fixtures(
        "fifa_world_cup",
        "2026",
        "England",
        "Panama",
    )[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path="tests/fixtures/betexplorer_match.html",
        url=None,
        status="available",
    )

    result = find_world_cup_candidates(db, home_team="England", away_team="Panama")

    assert result.status is CandidateStatus.READY
    assert (
        result.candidates[0].sources["betexplorer"].html_path
        == "tests/fixtures/betexplorer_match.html"
    )


def test_candidate_search_preserves_seeded_fixture_order_for_reverse_lookup(tmp_path):
    db = seeded_db(tmp_path)

    result = find_world_cup_candidates(db, home_team="Ghana", away_team="England")

    assert result.status is CandidateStatus.NEEDS_HTML
    assert result.candidates[0].home_team == "England"
    assert result.candidates[0].away_team == "Ghana"
