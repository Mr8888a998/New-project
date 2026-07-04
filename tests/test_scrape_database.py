from datetime import datetime, timezone

from handicap_ai.database import Database
from handicap_ai.scraping.models import SourceFetchRecord


def test_database_stores_source_fetch_records_idempotently(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    record = SourceFetchRecord(
        source="betexplorer",
        url="https://example.test/match",
        fetched_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
        status_code=200,
        cache_path="data/cache/betexplorer/match.html",
        content_hash="hash-one",
        error_message=None,
    )

    first_id = db.upsert_source_fetch(record)
    second_id = db.upsert_source_fetch(record)

    assert first_id == second_id
    rows = db.list_source_fetches("betexplorer")
    assert len(rows) == 1
    assert rows[0]["content_hash"] == "hash-one"


def test_database_records_scrape_jobs(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    job_id = db.insert_scrape_job(
        requested_home="England",
        requested_away="Panama",
        source="betexplorer",
        status="needs_confirmation",
        warnings=("multiple candidate matches found",),
    )

    row = db.get_scrape_job(job_id)
    assert row["requested_home"] == "England"
    assert row["requested_away"] == "Panama"
    assert row["source"] == "betexplorer"
    assert row["status"] == "needs_confirmation"
    assert row["warnings"] == "multiple candidate matches found"
