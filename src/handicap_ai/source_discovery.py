from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from handicap_ai.database import Database
from handicap_ai.names import normalize_team_name
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, SEASON_2026


class SourceLinkStatus(str, Enum):
    PENDING = "pending"
    AVAILABLE = "available"
    BLOCKED = "blocked"
    FAILED = "failed"
    MANUAL_REQUIRED = "manual_required"


@dataclass(frozen=True)
class SourceLinkResult:
    status: SourceLinkStatus
    fixture_id: int
    source: str
    html_path: str | None
    url: str | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryHttpResponse:
    url: str
    status_code: int | None
    text: str
    error_message: str | None = None


DEFAULT_LISTING_URLS = {
    "betexplorer": "https://www.betexplorer.com/football/world/world-championship-2026/fixtures/",
    "oddsportal": "https://www.oddsportal.com/football/world/world-championship-2026/",
}

DiscoveryHttpGet = Callable[[str], DiscoveryHttpResponse]


def default_listing_get(url: str) -> DiscoveryHttpResponse:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; handicap-ai-source-discovery/1.0)"
            )
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            text = response.read().decode(charset, errors="replace")
            return DiscoveryHttpResponse(
                url=response.geturl(),
                status_code=response.status,
                text=text,
            )
    except HTTPError as error:
        charset = error.headers.get_content_charset() if error.headers else "utf-8"
        text = error.read().decode(charset or "utf-8", errors="replace")
        return DiscoveryHttpResponse(url=url, status_code=error.code, text=text)
    except URLError as error:
        return DiscoveryHttpResponse(
            url=url,
            status_code=None,
            text="",
            error_message=str(error.reason),
        )


def register_fixture_source_url(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
    url: str,
    season: str = SEASON_2026,
) -> SourceLinkResult:
    source_key = source.lower()
    fixture = _single_fixture(db, home_team, away_team, season)
    fixture_id = int(fixture["fixture_id"])
    db.upsert_fixture_source_link(
        fixture_id=fixture_id,
        source=source_key,
        html_path=None,
        url=url,
        status=SourceLinkStatus.PENDING.value,
    )
    return SourceLinkResult(
        status=SourceLinkStatus.PENDING,
        fixture_id=fixture_id,
        source=source_key,
        html_path=None,
        url=url,
    )


def discover_fixture_source(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
    http_get: DiscoveryHttpGet = default_listing_get,
    season: str = SEASON_2026,
) -> SourceLinkResult:
    source_key = source.lower()
    listing_url = DEFAULT_LISTING_URLS.get(source_key)
    if listing_url is None:
        raise ValueError(f"unsupported source: {source}")

    fixture = _single_fixture(db, home_team, away_team, season)
    fixture_id = int(fixture["fixture_id"])
    response = http_get(listing_url)
    fetch_status, warning = _listing_fetch_status(response)
    if fetch_status is not SourceLinkStatus.PENDING:
        warnings = (warning,)
        available = _available_result(db, fixture_id, source_key, warnings)
        if available is not None:
            return available
        db.upsert_fixture_source_link(
            fixture_id=fixture_id,
            source=source_key,
            html_path=None,
            url=None,
            status=fetch_status.value,
        )
        return SourceLinkResult(
            status=fetch_status,
            fixture_id=fixture_id,
            source=source_key,
            html_path=None,
            url=None,
            warnings=warnings,
        )

    return discover_fixture_source_from_listing(
        db,
        home_team,
        away_team,
        source_key,
        response.text,
        response.url or listing_url,
        season=season,
    )


def discover_fixture_source_from_listing(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
    listing_html: str,
    base_url: str,
    season: str = SEASON_2026,
) -> SourceLinkResult:
    source_key = source.lower()
    fixture = _single_fixture(db, home_team, away_team, season)
    fixture_id = int(fixture["fixture_id"])
    url = _find_listing_url(
        listing_html,
        fixture["home_team"],
        fixture["away_team"],
        base_url,
    )
    if url is not None:
        db.upsert_fixture_source_link(
            fixture_id=fixture_id,
            source=source_key,
            html_path=None,
            url=url,
            status=SourceLinkStatus.PENDING.value,
        )
        return SourceLinkResult(
            status=SourceLinkStatus.PENDING,
            fixture_id=fixture_id,
            source=source_key,
            html_path=None,
            url=url,
        )

    warnings = (
        f"No source URL found for {fixture['home_team']} vs {fixture['away_team']}",
    )
    available = _available_result(db, fixture_id, source_key, warnings)
    if available is not None:
        return available
    db.upsert_fixture_source_link(
        fixture_id=fixture_id,
        source=source_key,
        html_path=None,
        url=None,
        status=SourceLinkStatus.MANUAL_REQUIRED.value,
    )
    return SourceLinkResult(
        status=SourceLinkStatus.MANUAL_REQUIRED,
        fixture_id=fixture_id,
        source=source_key,
        html_path=None,
        url=None,
        warnings=warnings,
    )


def _single_fixture(db: Database, home_team: str, away_team: str, season: str):
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


def _available_result(
    db: Database,
    fixture_id: int,
    source: str,
    warnings: tuple[str, ...] = (),
) -> SourceLinkResult | None:
    link = _source_link(db, fixture_id, source)
    if link is None or link["status"] != SourceLinkStatus.AVAILABLE.value:
        return None
    return SourceLinkResult(
        status=SourceLinkStatus.AVAILABLE,
        fixture_id=fixture_id,
        source=source,
        html_path=link["html_path"],
        url=link["url"],
        warnings=warnings,
    )


def _source_link(db: Database, fixture_id: int, source: str):
    for link in db.list_fixture_source_links(fixture_id):
        if link["source"].lower() == source.lower():
            return link
    return None


def _find_listing_url(
    listing_html: str,
    home_team: str,
    away_team: str,
    base_url: str,
) -> str | None:
    parser = _AnchorParser()
    parser.feed(listing_html)
    home_normalized = normalize_team_name(home_team)
    away_normalized = normalize_team_name(away_team)

    for href, text in parser.links:
        text_normalized = normalize_team_name(text)
        href_normalized = normalize_team_name(href)
        if _contains_team_pair(
            text_normalized,
            home_normalized,
            away_normalized,
        ) or _contains_team_pair(href_normalized, home_normalized, away_normalized):
            return urljoin(base_url, href)
    return None


def _listing_fetch_status(
    response: DiscoveryHttpResponse,
) -> tuple[SourceLinkStatus, str]:
    if response.error_message:
        return SourceLinkStatus.FAILED, response.error_message
    if response.status_code in {401, 402, 403, 429}:
        return SourceLinkStatus.BLOCKED, "listing fetch blocked by source"
    lowered = response.text.lower()
    if "captcha" in lowered or "access denied" in lowered or "login" in lowered:
        return SourceLinkStatus.BLOCKED, "listing fetch blocked by source"
    if response.status_code is None or response.status_code >= 400:
        return (
            SourceLinkStatus.FAILED,
            f"listing fetch failed with status {response.status_code}",
        )
    return SourceLinkStatus.PENDING, ""


def _contains_team_pair(
    text_normalized: str,
    home_normalized: str,
    away_normalized: str,
) -> bool:
    searchable = f" {text_normalized} "
    home_position = searchable.find(f" {home_normalized} ")
    away_position = searchable.find(f" {away_normalized} ")
    return home_position >= 0 and away_position >= 0 and home_position != away_position


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._active_href: str | None = None
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._active_href = href
            self._active_text = []

    def handle_data(self, data: str) -> None:
        if self._active_href is not None:
            self._active_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._active_href is None:
            return
        self.links.append((self._active_href, " ".join(self._active_text)))
        self._active_href = None
        self._active_text = []
