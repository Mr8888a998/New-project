# Live Source Discovery and Fetch Design

## Goal

Add a conservative live-source layer on top of the existing World Cup candidate
workflow. A user should be able to enter only home and away teams, find the
seeded fixture, discover or register BetExplorer/OddsPortal source URLs, fetch
HTML on demand, cache it locally, and then run the existing saved-HTML analysis.

This feature extends the current saved-HTML-backed workflow. It does not make
live scraping mandatory for analysis.

## Scope

This phase includes:

- Source URL discovery for seeded World Cup fixtures.
- Manual source URL registration when automatic discovery is incomplete.
- User-triggered HTML fetch and local cache storage.
- Fixture source-link status updates: `pending`, `available`, `blocked`,
  `failed`, and `manual_required`.
- CLI and UI controls for source discovery and source fetching.
- Reuse of existing BetExplorer/OddsPortal parsers and `analyze_saved_html`.

This phase does not include:

- Login, account sessions, paid pages, CAPTCHA solving, anti-bot bypass, or
  browser-extension automation.
- Background polling.
- Automated betting.
- Tests that depend on live BetExplorer/OddsPortal availability.

## Product Behavior

The normal user path becomes:

1. Enter home and away teams in the dashboard.
2. Click `Find candidates`.
3. If no saved HTML exists, click `Discover sources`.
4. The system records candidate source URLs or a clear warning.
5. Click `Fetch source HTML` for a selected source.
6. If fetch succeeds, cached HTML becomes the candidate `html_path`.
7. Click `Analyze saved HTML`.

Blocked-site fallback:

1. Discovery or fetch reports `blocked` / `failed`.
2. UI keeps the URL and warning visible.
3. User manually saves source HTML.
4. User pastes the saved local path and analyzes it through the existing flow.

## Architecture

### Source Discovery Service

Create a service module that accepts:

- `Database`
- fixture id or home/away teams
- selected sources, initially `betexplorer` and `oddsportal`

It returns a `SourceDiscoveryResult` with:

- source name
- discovered URL, when found
- status
- warnings
- updated fixture source links

The first implementation should support two discovery modes:

- **Direct URL registration:** user provides a source and URL; the system records
  it against the fixture.
- **Fixture-page discovery:** for known competition fixture pages, fetch or load
  a source listing page and parse links that match the two team names.

Direct URL registration is the stable base. Fixture-page discovery is best
effort and must degrade to `manual_required` without blocking the rest of the
workflow.

### Fetch Cache Service

Create a cache-aware fetch service that:

- fetches one user-selected URL at a time
- uses a conservative timeout
- stores HTML under ignored `data/cache/<source>/...`
- records `SourceFetchRecord` through the existing `source_fetches` table
- updates `fixture_source_links.html_path` when a fetch is successful
- marks the source link `blocked` or `failed` when fetch or parser checks fail

Saved fixture tests should exercise this service through fixture HTML or mocked
HTTP responses, not through real network calls.

### Existing Parser Reuse

The live fetch layer should not invent a second parser path. Once HTML exists on
disk, analysis still flows through:

```text
cached html path -> analyze_saved_html -> source adapter -> normalized bundle
```

This keeps BetExplorer and OddsPortal parsing inside the existing adapter
modules.

### Database Use

Reuse existing tables:

- `fixture_source_links`
- `source_fetches`
- `scrape_jobs`

Add helper methods only if they remove repeated SQL or make tests clearer. The
existing `upsert_fixture_source_link` shape is enough for the first version.

Fixture source-link status meanings:

- `pending`: URL known, HTML not cached.
- `available`: HTML path exists and can be analyzed.
- `blocked`: source appears inaccessible because of login, CAPTCHA, paywall, or
  anti-bot response.
- `failed`: request, parse, or storage failed for a non-policy reason.
- `manual_required`: automatic discovery did not find a reliable URL.

## CLI

Add commands shaped like:

```bash
handicap-ai discover-sources --db data/handicap_ai.sqlite --home England --away Ghana
handicap-ai register-source-url --db data/handicap_ai.sqlite --home England --away Ghana --source betexplorer --url https://...
handicap-ai fetch-source-html --db data/handicap_ai.sqlite --home England --away Ghana --source betexplorer
```

The commands should print source status, URL, cache path, and warnings. They
should not auto-analyze unless explicitly told to in a later phase.

## UI

Extend the candidate confirmation panel with source controls:

- source rows for BetExplorer and OddsPortal
- status badge per source
- URL display or manual URL input
- `Discover sources` button
- `Fetch source HTML` button per source
- cached HTML path when available

The existing `HTML path` input remains editable. If a fetch succeeds, the UI may
populate that field with the cached path.

The UI should never hide manual saved-HTML fallback. If a site is blocked, the
user should still see exactly what to do next.

## Error Handling

Discovery failures:

- Return partial results for other sources.
- Store `manual_required` with a warning when a link cannot be found.
- Do not overwrite an existing `available` HTML path with a failed discovery.

Fetch failures:

- Record the failed `source_fetches` row when possible.
- Do not replace a working cached HTML file with a failed fetch.
- Mark `blocked` only for recognizable blocked/login/CAPTCHA/paywall-like
  responses. Otherwise mark `failed`.

Parser checks:

- After fetching, run the matching adapter parser as a sanity check.
- If the parser cannot find a match container or core markets, keep the cached
  file for debugging but do not mark the link `available`.

## Testing Strategy

No automated test may depend on live BetExplorer or OddsPortal.

Unit tests:

- source URL registration updates the right fixture link
- discovery parses fixture-list HTML links by team names
- discovery reports `manual_required` when no link matches
- fetch service writes cached HTML and records `source_fetches`
- blocked/failed fetches do not overwrite existing available HTML
- fetched malformed HTML is not marked `available`

CLI tests:

- register source URL
- discover sources from fixture HTML through an injected/local fixture page
- fetch source HTML with mocked/local response

UI tests:

- dashboard renders source controls
- source discovery endpoint returns source rows
- fetch endpoint returns cached path and updates candidate source status

Manual smoke:

- try a real BetExplorer fixture URL if accessible
- try a real OddsPortal URL if accessible
- confirm blocked pages surface a clear warning and leave manual path usable

## Implementation Notes

Prefer small, isolated modules:

- `source_discovery.py` for fixture source discovery and registration
- `source_fetch.py` for URL fetch/cache/status logic
- current adapters remain responsible for parsing match pages

Live HTTP should be a thin dependency that can be replaced in tests. The first
version can use a simple callable or tiny client object rather than a large
framework.

## Acceptance Criteria

- Existing saved-HTML candidate workflow still passes.
- User can register a BetExplorer/OddsPortal URL for a seeded fixture.
- User can fetch that URL into `data/cache` and see the cached path in CLI/UI.
- Candidate status becomes ready only when cached HTML exists and parser sanity
  checks pass.
- Blocked or failed sources produce explicit warnings and keep manual HTML
  fallback available.
- Full test suite passes without live network access.
