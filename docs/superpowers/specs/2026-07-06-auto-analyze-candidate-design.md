# Auto Analyze Candidate Design

## Goal

Build an automatic analysis path where the user enters only home team, away team,
and source, then receives the best handicap, total, and 1X2 picks when the
system can locate or fetch source HTML.

## Scope

This feature extends the current World Cup candidate and source-link workflow.
It does not introduce a new prediction model, continuous crawling, betting
automation, login handling, CAPTCHA bypassing, or paid-source access.

The first implementation supports:

- FIFA World Cup 2026 seeded group-stage fixtures.
- `betexplorer` and `oddsportal`.
- Existing cached HTML analysis.
- User-triggered source discovery and source HTML fetch.
- Clear fallback statuses when live discovery or fetch is blocked.

## User Experience

The dashboard adds one primary action: `Auto analyze`.

The user fills:

- Home team.
- Away team.
- Source.

When clicked, the dashboard shows the automatic workflow as progress text:

1. Candidate confirmation.
2. Source discovery when no cached HTML exists.
3. Source fetch when a source URL exists.
4. Saved HTML analysis.
5. Result or manual action required.

Successful output reuses the existing recommendation cards:

- Handicap.
- Total.
- 1X2.
- Confidence values.
- Coverage.
- Data quality.
- Risk tags.

If automation cannot finish, the UI keeps the existing manual controls visible
and displays the source status, URL, HTML path, and warnings returned by the
server.

## API Design

Add endpoint:

```text
POST /api/auto-analyze-candidate
```

Request:

```json
{
  "home_team": "England",
  "away_team": "Panama",
  "source": "betexplorer"
}
```

Response shape:

```json
{
  "status": "analysis_ready",
  "stage": "analyzed",
  "warnings": [],
  "candidate": {
    "fixture_id": 69,
    "group_name": "L",
    "home_team": "England",
    "away_team": "Panama",
    "kickoff_time": null,
    "status": "seeded",
    "sources": {}
  },
  "source_link": {
    "fixture_id": 69,
    "source": "betexplorer",
    "status": "available",
    "url": "https://www.betexplorer.com/...",
    "html_path": "data/cache/betexplorer/fixture-69-abc.html",
    "warnings": []
  },
  "analysis": {
    "match": "England vs Panama",
    "coverage": "complete",
    "missing_markets": [],
    "risk_tags": [],
    "picks": {
      "handicap": "away",
      "total": "under",
      "1x2": "home"
    },
    "confidence": {
      "handicap": "medium",
      "total": "medium",
      "1x2": "low"
    },
    "data_quality": 1.0
  }
}
```

`analysis` is `null` when automation cannot finish.

Statuses:

- `analysis_ready`: cached or freshly fetched HTML was analyzed.
- `invalid_team`: at least one team cannot be resolved.
- `not_in_group_stage`: both teams exist, but no seeded fixture exists.
- `needs_manual_source`: no source URL could be found automatically.
- `source_pending`: source URL exists but fetch did not produce usable HTML.
- `fetch_blocked`: source responded with login, CAPTCHA, access denied, 401,
  402, 403, or 429.
- `fetch_failed`: source fetch, cache write, parser validation, or final URL
  validation failed.

Stages:

- `candidate_checked`.
- `source_discovered`.
- `source_fetched`.
- `analyzed`.
- `manual_required`.

## Server Flow

The endpoint executes this sequence:

1. Call `find_world_cup_candidates()`.
2. Return `invalid_team` or `not_in_group_stage` directly when candidate search
   cannot produce a fixture.
3. Select the single fixture for the requested team pair.
4. Check the selected source link.
5. If the selected source already has `status=available` and the HTML path
   exists, call `analyze_saved_html()`.
6. If no usable cached HTML exists, call `discover_fixture_source()`.
7. If discovery returns `manual_required`, `failed`, or `blocked` without a URL,
   return `needs_manual_source`, `fetch_failed`, or `fetch_blocked`.
8. If a URL is available or pending, call `fetch_fixture_source_html()`.
9. If fetch returns `available` with an existing HTML path, call
   `analyze_saved_html()`.
10. Otherwise return a manual-action status with source-link details.

The endpoint must not accept a client-supplied `cache_dir`. It uses the
server-side `cache_dir` passed to `create_app()`.

For deterministic tests, `create_app()` may accept optional server-side
callables for auto discovery and auto fetch. Production defaults use the real
network helpers. Test callables are never exposed through the request payload.

## Source Selection

The request has an explicit `source` field. The endpoint does not silently try
both sources in the first version. This keeps behavior understandable and makes
warnings actionable.

The UI default remains `betexplorer`, with `oddsportal` available in the source
select.

## Error Handling

Expected automation problems return HTTP 200 with a non-ready status. Examples:

- Site blocked fetch.
- Listing page could not be parsed.
- Source URL not discovered.
- Cached or fetched HTML does not match the requested fixture.
- Missing markets.

Invalid request-like conditions return HTTP 400:

- Unsupported source.
- Malformed source URL already stored in the database.

Unknown teams and non-group-stage pairs are expected product states and return
HTTP 200 with `invalid_team` or `not_in_group_stage`.

The endpoint preserves existing source-link safeguards:

- Source validation only allows supported sources.
- URL validation only allows source-owned domains.
- Final fetch URL is revalidated after redirects.
- Failed discovery or fetch must not erase an existing available HTML path.
- Client cannot set cache path.

## Frontend Design

Add one button beside existing analysis actions:

```text
Auto analyze
```

Button behavior:

- Reads `#home-team`, `#away-team`, and `#source`.
- Disables source action buttons while the request is running.
- Sets `#form-message` to the current automation stage.
- Calls `/api/auto-analyze-candidate`.
- If `analysis` exists, renders the existing result cards exactly like saved
  HTML analysis.
- Always renders candidate and source-link panels from the response when
  present.
- If `analysis` is null, leaves manual source URL, discover, fetch, and HTML
  path controls available for the next action.

The UI should not add new instructional blocks or marketing copy. Existing
status panels are enough.

## Testing Strategy

Backend tests:

- Cached available HTML returns `analysis_ready` without calling live discovery.
- No cached HTML but injected discovery and fetch callables succeed.
- Discovery cannot find a source URL and returns `needs_manual_source`.
- Fetch blocked returns `fetch_blocked` and no analysis.
- Unsupported source returns HTTP 400.
- Existing available HTML survives a failed automation retry.

Frontend/API tests:

- Dashboard renders `Auto analyze`.
- The dashboard script calls `/api/auto-analyze-candidate`.
- Successful auto-analysis populates the existing recommendation response shape.
- Failed automation returns source-link warnings and leaves `analysis` null.

Manual browser smoke:

- Start the UI on a local port.
- Open the dashboard.
- Enter `England` and `Panama`.
- Click `Auto analyze` against a database with cached fixture HTML.
- Confirm the three recommendation cards are populated.

## Non-Goals

- Real-time in-play or rolling-ball automation.
- Multiple-source voting.
- Training a model.
- Bet placement.
- Background crawling.
- CAPTCHA, login, paywall, or anti-bot bypass.
