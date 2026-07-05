from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sqlite3
from typing import TypeAlias

import httpx

from handicap_ai.adapters.betexplorer import BetExplorerHtmlAdapter
from handicap_ai.adapters.oddsportal import OddsPortalHtmlAdapter
from handicap_ai.database import Database
from handicap_ai.names import normalize_team_name
from handicap_ai.scraping.models import SourceFetchRecord
from handicap_ai.source_discovery import (
    SourceLinkResult,
    SourceLinkStatus,
    normalize_source,
    validate_source_url,
)
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, SEASON_2026


@dataclass(frozen=True)
class FetchHttpResponse:
    url: str
    status_code: int | None
    text: str
    error_message: str | None = None


FetchHttpGet = Callable[[str], FetchHttpResponse]
HtmlAdapter: TypeAlias = type[BetExplorerHtmlAdapter] | type[OddsPortalHtmlAdapter]


def default_http_get(url: str) -> FetchHttpResponse:
    try:
        with httpx.Client(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "handicap-ai/0.1"},
        ) as client:
            response = client.get(url)
        return FetchHttpResponse(
            url=str(response.url),
            status_code=response.status_code,
            text=response.text,
            error_message=None,
        )
    except httpx.HTTPError as error:
        return FetchHttpResponse(
            url=url,
            status_code=None,
            text="",
            error_message=str(error),
        )


def fetch_fixture_source_html(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
    cache_dir: str | Path,
    http_get: FetchHttpGet = default_http_get,
    season: str = SEASON_2026,
) -> SourceLinkResult:
    source_key = normalize_source(source)
    fixture = _single_fixture(db, home_team, away_team, season)
    fixture_id = int(fixture["fixture_id"])
    link = _source_link(db, fixture_id, source_key)
    if link is None or not link["url"]:
        raise ValueError(
            f"no registered URL for {source_key} {home_team} vs {away_team}"
        )

    registered_url = validate_source_url(source_key, str(link["url"]))
    response = http_get(registered_url)
    status, warning = _response_status(response)
    cached_path, content_hash = _write_cache_if_fetch_succeeded(
        cache_dir,
        source_key,
        fixture_id,
        response,
    )

    if status is SourceLinkStatus.PENDING or _can_parse_text_blocked_response(
        response, status
    ):
        parse_warning = _parse_warning(source_key, response.text, fixture, db, season)
        if parse_warning is None:
            _record_source_fetch(
                db,
                source_key,
                response.url or registered_url,
                response,
                cached_path,
                content_hash,
                response.error_message,
            )
            html_path = str(cached_path) if cached_path is not None else None
            db.upsert_fixture_source_link(
                fixture_id=fixture_id,
                source=source_key,
                html_path=html_path,
                url=registered_url,
                status=SourceLinkStatus.AVAILABLE.value,
            )
            return SourceLinkResult(
                status=SourceLinkStatus.AVAILABLE,
                fixture_id=fixture_id,
                source=source_key,
                html_path=html_path,
                url=registered_url,
            )
        if status is SourceLinkStatus.PENDING:
            status = SourceLinkStatus.FAILED
            warning = parse_warning

    if status is not SourceLinkStatus.PENDING:
        _record_source_fetch(
            db,
            source_key,
            response.url or registered_url,
            response,
            cached_path,
            content_hash,
            response.error_message or warning,
        )
        warnings = (warning,)
        html_path = _available_html_path(db, fixture_id, source_key)
        _mark_link_unless_available(
            db,
            fixture_id,
            source_key,
            registered_url,
            status,
        )
        return SourceLinkResult(
            status=status,
            fixture_id=fixture_id,
            source=source_key,
            html_path=html_path,
            url=registered_url,
            warnings=warnings,
        )
    raise RuntimeError("unreachable fetch status")


def _response_status(response: FetchHttpResponse) -> tuple[SourceLinkStatus, str]:
    if response.error_message:
        return SourceLinkStatus.FAILED, response.error_message
    if response.status_code in {401, 402, 403, 429}:
        return SourceLinkStatus.BLOCKED, "source fetch blocked by source"
    lowered = response.text.lower()
    if "captcha" in lowered or "access denied" in lowered or "login" in lowered:
        return SourceLinkStatus.BLOCKED, "source fetch blocked by source"
    if response.status_code is None or response.status_code >= 400:
        return (
            SourceLinkStatus.FAILED,
            f"source fetch failed with status {response.status_code}",
        )
    return SourceLinkStatus.PENDING, ""


def _can_parse_text_blocked_response(
    response: FetchHttpResponse,
    status: SourceLinkStatus,
) -> bool:
    return (
        status is SourceLinkStatus.BLOCKED
        and response.error_message is None
        and response.status_code is not None
        and 200 <= response.status_code < 400
    )


def _parse_warning(
    source: str,
    html: str,
    fixture: sqlite3.Row,
    db: Database,
    season: str,
) -> str | None:
    adapter = _adapter_for_source(source)
    try:
        bundle, coverage = adapter(Path("unused")).parse_html(html)
    except ValueError as error:
        return str(error)

    if not _matches_fixture(
        bundle.match.home_team,
        bundle.match.away_team,
        fixture,
        db,
        season,
    ):
        return (
            f"fetched match {bundle.match.home_team} vs {bundle.match.away_team} "
            f"does not match {fixture['home_team']} vs {fixture['away_team']}"
        )
    if not coverage.is_complete:
        missing = ", ".join(coverage.missing_markets)
        return f"{source} parser missing markets: {missing}"
    return None


def _cache_path(
    cache_dir: str | Path,
    source: str,
    fixture_id: int,
    digest: str,
) -> Path:
    safe_source = re.sub(r"[^a-z0-9._-]+", "-", source.lower()).strip("-")
    safe_source = safe_source or "source"
    return Path(cache_dir) / safe_source / f"fixture-{fixture_id}-{digest}.html"


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


def _source_link(db: Database, fixture_id: int, source: str) -> sqlite3.Row | None:
    for link in db.list_fixture_source_links(fixture_id):
        if link["source"].lower() == source.lower():
            return link
    return None


def _matches_fixture(
    parsed_home_team: str,
    parsed_away_team: str,
    fixture: sqlite3.Row,
    db: Database,
    season: str,
) -> bool:
    parsed_pair = (
        normalize_team_name(parsed_home_team),
        normalize_team_name(parsed_away_team),
    )
    home_candidates = _normalized_team_name_candidates(
        db,
        fixture["home_team"],
        season,
    )
    away_candidates = _normalized_team_name_candidates(
        db,
        fixture["away_team"],
        season,
    )
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


def _available_html_path(db: Database, fixture_id: int, source: str) -> str | None:
    link = _source_link(db, fixture_id, source)
    if link is None or link["status"] != SourceLinkStatus.AVAILABLE.value:
        return None
    return link["html_path"]


def _record_source_fetch(
    db: Database,
    source: str,
    url: str,
    response: FetchHttpResponse,
    cached_path: Path | None,
    content_hash: str | None,
    error_message: str | None,
) -> None:
    db.upsert_source_fetch(
        SourceFetchRecord(
            source=source,
            url=url,
            fetched_at=datetime.now(timezone.utc),
            status_code=response.status_code,
            cache_path=str(cached_path) if cached_path is not None else None,
            content_hash=content_hash,
            error_message=error_message,
        )
    )


def _write_cache_if_fetch_succeeded(
    cache_dir: str | Path,
    source: str,
    fixture_id: int,
    response: FetchHttpResponse,
) -> tuple[Path | None, str | None]:
    if (
        response.error_message is not None
        or response.status_code is None
        or response.status_code >= 400
    ):
        return None, None

    content_hash = hashlib.sha256(response.text.encode("utf-8")).hexdigest()
    path = _cache_path(cache_dir, source, fixture_id, content_hash)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(response.text, encoding="utf-8")
    return path, content_hash


def _mark_link_unless_available(
    db: Database,
    fixture_id: int,
    source: str,
    url: str,
    status: SourceLinkStatus,
) -> None:
    existing = _source_link(db, fixture_id, source)
    if existing is not None and existing["status"] == SourceLinkStatus.AVAILABLE.value:
        return
    db.upsert_fixture_source_link(
        fixture_id=fixture_id,
        source=source,
        html_path=None,
        url=url,
        status=status.value,
    )


def _adapter_for_source(source: str) -> HtmlAdapter:
    if source.lower() == BetExplorerHtmlAdapter.source_name:
        return BetExplorerHtmlAdapter
    if source.lower() == OddsPortalHtmlAdapter.source_name:
        return OddsPortalHtmlAdapter
    raise ValueError(f"unsupported source: {source}")
