from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sqlite3
from typing import TypeAlias

from handicap_ai.adapters.betexplorer import BetExplorerHtmlAdapter
from handicap_ai.adapters.oddsportal import OddsPortalHtmlAdapter
from handicap_ai.database import Database
from handicap_ai.names import normalize_team_name
from handicap_ai.scraping.models import SourceFetchRecord
from handicap_ai.source_discovery import SourceLinkResult, SourceLinkStatus, normalize_source
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, SEASON_2026


HtmlAdapter: TypeAlias = type[BetExplorerHtmlAdapter] | type[OddsPortalHtmlAdapter]


@dataclass(frozen=True)
class ManualHtmlValidation:
    fixture_id: int
    source: str
    warning: str | None


def save_manual_fixture_html(
    db: Database,
    *,
    home_team: str,
    away_team: str,
    source: str,
    html: str,
    cache_dir: str | Path,
    season: str = SEASON_2026,
) -> SourceLinkResult:
    source_key = normalize_source(source)
    fixture = _single_fixture(db, home_team, away_team, season)
    fixture_id = int(fixture["fixture_id"])
    validation = _validate_manual_html(db, source_key, html, fixture, season)
    manual_url = f"manual://fixture/{fixture_id}/{source_key}"
    if validation.warning is not None:
        db.upsert_source_fetch(
            SourceFetchRecord(
                source=source_key,
                url=manual_url,
                fetched_at=datetime.now(timezone.utc),
                status_code=None,
                cache_path=None,
                content_hash=_content_hash(html),
                error_message=validation.warning,
            )
        )
        return SourceLinkResult(
            status=SourceLinkStatus.FAILED,
            fixture_id=fixture_id,
            source=source_key,
            html_path=None,
            url=None,
            warnings=(validation.warning,),
        )

    cached_path = _write_manual_cache(cache_dir, source_key, fixture_id, html)
    db.upsert_source_fetch(
        SourceFetchRecord(
            source=source_key,
            url=manual_url,
            fetched_at=datetime.now(timezone.utc),
            status_code=200,
            cache_path=str(cached_path),
            content_hash=_content_hash(html),
            error_message=None,
        )
    )
    existing_url = _existing_url(db, fixture_id, source_key)
    db.upsert_fixture_source_link(
        fixture_id=fixture_id,
        source=source_key,
        html_path=str(cached_path),
        url=existing_url,
        status=SourceLinkStatus.AVAILABLE.value,
    )
    return SourceLinkResult(
        status=SourceLinkStatus.AVAILABLE,
        fixture_id=fixture_id,
        source=source_key,
        html_path=str(cached_path),
        url=existing_url,
    )


def _validate_manual_html(
    db: Database,
    source: str,
    html: str,
    fixture: sqlite3.Row,
    season: str,
) -> ManualHtmlValidation:
    adapter = _adapter_for_source(source)
    try:
        bundle, coverage = adapter(Path("unused")).parse_html(html)
    except ValueError as error:
        return ManualHtmlValidation(int(fixture["fixture_id"]), source, str(error))

    if not _matches_fixture(
        db,
        season,
        bundle.match.home_team,
        bundle.match.away_team,
        fixture,
    ):
        return ManualHtmlValidation(
            int(fixture["fixture_id"]),
            source,
            (
                f"manual HTML match {bundle.match.home_team} vs {bundle.match.away_team} "
                f"does not match {fixture['home_team']} vs {fixture['away_team']}"
            ),
        )
    if not coverage.is_complete:
        missing = ", ".join(coverage.missing_markets)
        return ManualHtmlValidation(
            int(fixture["fixture_id"]),
            source,
            f"{source} parser missing markets: {missing}",
        )
    return ManualHtmlValidation(int(fixture["fixture_id"]), source, None)


def _single_fixture(
    db: Database,
    home_team: str,
    away_team: str,
    season: str,
) -> sqlite3.Row:
    resolved_home = db.resolve_tournament_team(FIFA_WORLD_CUP, season, home_team)
    resolved_away = db.resolve_tournament_team(FIFA_WORLD_CUP, season, away_team)
    if resolved_home is None:
        raise ValueError(f"Unknown team: {home_team}")
    if resolved_away is None:
        raise ValueError(f"Unknown team: {away_team}")

    fixtures = db.find_tournament_fixtures(
        FIFA_WORLD_CUP,
        season,
        resolved_home["team_name"],
        resolved_away["team_name"],
    )
    if not fixtures:
        raise ValueError(
            f"No World Cup {season} fixture found for "
            f"{resolved_home['team_name']} vs {resolved_away['team_name']}"
        )
    if len(fixtures) > 1:
        raise ValueError(
            f"Multiple World Cup {season} fixtures found for "
            f"{resolved_home['team_name']} vs {resolved_away['team_name']}"
        )
    return fixtures[0]


def _matches_fixture(
    db: Database,
    season: str,
    parsed_home_team: str,
    parsed_away_team: str,
    fixture: sqlite3.Row,
) -> bool:
    parsed_pair = (
        normalize_team_name(parsed_home_team),
        normalize_team_name(parsed_away_team),
    )
    home_candidates = _normalized_team_name_candidates(db, fixture["home_team"], season)
    away_candidates = _normalized_team_name_candidates(db, fixture["away_team"], season)
    return (
        parsed_pair[0] in home_candidates and parsed_pair[1] in away_candidates
    ) or (parsed_pair[0] in away_candidates and parsed_pair[1] in home_candidates)


def _normalized_team_name_candidates(
    db: Database,
    team_name: str,
    season: str,
) -> set[str]:
    normalized_name = normalize_team_name(team_name)
    candidates = {normalized_name}
    rows = db.execute(
        """
        SELECT normalized_alias
        FROM tournament_team_aliases
        WHERE tournament = ?
          AND season = ?
          AND normalized_team_name = ?
        """,
        (FIFA_WORLD_CUP, season, normalized_name),
    )
    candidates.update(row["normalized_alias"] for row in rows)
    return candidates


def _write_manual_cache(
    cache_dir: str | Path,
    source: str,
    fixture_id: int,
    html: str,
) -> Path:
    digest = _content_hash(html)
    safe_source = re.sub(r"[^a-z0-9._-]+", "-", source.lower()).strip("-")
    path = Path(cache_dir) / "manual" / safe_source / f"fixture-{fixture_id}-{digest}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def _existing_url(db: Database, fixture_id: int, source: str) -> str | None:
    for link in db.list_fixture_source_links(fixture_id):
        if link["source"].lower() == source.lower():
            return link["url"]
    return None


def _content_hash(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def _adapter_for_source(source: str) -> HtmlAdapter:
    if source == BetExplorerHtmlAdapter.source_name:
        return BetExplorerHtmlAdapter
    if source == OddsPortalHtmlAdapter.source_name:
        return OddsPortalHtmlAdapter
    raise ValueError(f"unsupported source: {source}")
