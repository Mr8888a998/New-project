from datetime import datetime, timezone

from handicap_ai.scraping.models import (
    MarketCoverage,
    MatchCandidate,
    SourceCoverage,
    SourceFetchRecord,
    WizardState,
)


def test_source_coverage_flags_missing_markets():
    coverage = SourceCoverage(
        source="betexplorer",
        one_x_two=MarketCoverage(found=True, rows=6),
        handicap=MarketCoverage(found=True, rows=4),
        totals=MarketCoverage(found=False, rows=0),
        warnings=("totals table missing",),
    )

    assert coverage.is_complete is False
    assert coverage.missing_markets == ("totals",)
    assert "scrape_market_missing" in coverage.risk_tags


def test_source_coverage_complete_when_all_markets_found():
    coverage = SourceCoverage(
        source="betexplorer",
        one_x_two=MarketCoverage(found=True, rows=6),
        handicap=MarketCoverage(found=True, rows=4),
        totals=MarketCoverage(found=True, rows=4),
    )

    assert coverage.is_complete is True
    assert coverage.missing_markets == ()
    assert coverage.risk_tags == ()


def test_wizard_state_requires_confirmation_for_ambiguous_candidates():
    state = WizardState(
        candidates=(
            MatchCandidate("betexplorer", "1", "England", "Panama", None, "url-a"),
            MatchCandidate("betexplorer", "2", "England U21", "Panama", None, "url-b"),
        ),
        coverage=None,
    )

    assert state.needs_confirmation is True
    assert state.reason == "multiple candidate matches found"


def test_source_fetch_record_has_stable_success_flag():
    fetched_at = datetime(2026, 7, 5, tzinfo=timezone.utc)
    record = SourceFetchRecord(
        source="betexplorer",
        url="https://www.betexplorer.com/match",
        fetched_at=fetched_at,
        status_code=200,
        cache_path="data/cache/betexplorer.html",
        content_hash="abc123",
        error_message=None,
    )

    assert record.ok is True
