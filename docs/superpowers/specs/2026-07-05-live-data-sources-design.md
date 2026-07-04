# Live Data Sources Design

## Goal

Extend Handicap AI from a fixture and CSV MVP into a practical data-ingestion
tool where the user enters only home and away team names, then the system can:

- fetch current match odds from an API source,
- import larger historical datasets from CSV or Excel files,
- combine current lines with local historical samples,
- output the best available picks for Asian handicap, over/under, and 1X2.

This version is still decision support. It should show data quality and no-bet
states clearly rather than forcing an answer when a source is incomplete.

## Approved Source Strategy

Use two source families in this phase:

1. API source for current and upcoming matches.
2. CSV or Excel imports for historical odds and result data.

Web scraping of BetExplorer, OddsPortal, or similar pages remains out of scope
for this phase. It can be added later behind the same adapter interface if a
stable and permitted access path is confirmed.

## Primary API Adapter

Add a configurable odds API adapter, initially targeting The Odds API v4 because
its public documentation exposes football/soccer odds with market families that
map cleanly to the existing engine:

- `h2h` for 1X2-like moneyline outcomes.
- `spreads` for handicap-style lines where available.
- `totals` for over/under lines where available.

The adapter must not assume every event has every market. If a source returns
only 1X2 and totals, handicap should become no-bet with a missing-market risk
tag. If a source returns spread markets that are not true Asian handicap quarter
lines, the adapter should store them as normalized handicap-style lines and mark
the data source in the report.

Configuration:

- API key is read from `ODDS_API_KEY` by default.
- Optional base URL allows fixture tests and future provider swaps.
- Optional sport key defaults to soccer-oriented keys selected by the user or
  command line.
- Region and bookmaker filters are configurable.

The implementation must avoid hardcoding secrets. API keys are never written to
logs, reports, SQLite, or committed files.

## Historical CSV and Excel Imports

Enhance historical imports so the user can point the tool at either one file or
a folder of downloaded datasets.

Supported inputs:

- Existing Football-Data CSV files.
- Football-Data-style Excel files when a supported workbook parser is present.
- A generic normalized CSV template for user-maintained data.

The importer should detect supported file types and skip unsupported files with
a clear message. It should be idempotent: importing the same folder twice should
not duplicate matches or odds rows.

The first implementation should support folder import before adding advanced
spreadsheet UI features. Excel support may use `openpyxl` if available through
project dependencies.

## User Experience

New or extended CLI commands:

```text
handicap-ai import-history-folder --db data/handicap_ai.sqlite --path data/history
handicap-ai fetch-api-match --db data/handicap_ai.sqlite --home England --away Panama
handicap-ai analyze-live --db data/handicap_ai.sqlite --home England --away Panama
```

`analyze-live` should:

1. Resolve the requested teams against local history.
2. Fetch current API events and odds for the same team pair.
3. Ingest the fetched current match and odds into SQLite.
4. Build current line features.
5. Retrieve local historical similarity samples.
6. Output one recommendation per market.

Example output:

```text
England vs Panama

Handicap pick: Panama +2.25
Total pick: Under 3.0
1X2 pick: England win

Data quality: 0.72
Risk tags:
- current_api_missing_opening_line
- historical_sample_small
- recheck_near_kickoff
```

If the API cannot find a match, the command should report the searched team
names, sport key, region, and source. If multiple API events match, it should
choose the nearest upcoming kickoff by default and show the chosen event.

## Normalization Rules

The API adapter should convert provider payloads into existing
`NormalizedMatchBundle` records.

Match fields:

- source match id uses a stable provider id with a source prefix.
- home and away team names are preserved as provider display names.
- normalized names are still handled by the database and resolver.
- kickoff time comes from the provider when available.
- status is scheduled unless a completed result is explicitly present.

Market fields:

- `h2h` maps to `OneXTwoLineRecord`.
- `spreads` maps to `AsianHandicapLineRecord` with source metadata preserved.
- `totals` maps to `TotalsLineRecord`.
- captured time is the fetch time when the provider does not include a market
  timestamp.
- API odds are treated as current or closing-like snapshots, not true opening
  lines, unless a provider explicitly supplies opening prices.

Because many current-odds APIs do not provide historical open-to-close movement,
data quality should be reduced when opening lines are missing.

## Data Quality and Risk Tags

Add or reuse risk tags for live-data scenarios:

- `current_api_missing_market`
- `current_api_missing_opening_line`
- `api_rate_limited`
- `api_match_ambiguous`
- `api_match_not_found`
- `historical_import_partial`
- `historical_sample_small`
- `source_market_not_asian_handicap`

Recommendation behavior:

- If a market is missing current odds, output no-bet for that market.
- If current odds exist but historical samples are weak, allow a low-confidence
  pick only when rule-based signals are strong; otherwise no-bet.
- If only 1X2 is available, handicap and total should not infer picks from 1X2
  alone.

## Error Handling

API failures:

- On 401 or invalid key, report that `ODDS_API_KEY` is missing or invalid.
- On 429 or quota exhaustion, report `api_rate_limited` and keep cached data.
- On network timeout, report the source failure and avoid overwriting newer
  cached snapshots.
- On malformed provider payloads, fail that source adapter without crashing
  other importers.

Import failures:

- One bad file should not abort a full folder import.
- The command should summarize imported files, skipped files, matches imported,
  and parser errors.
- Unsupported columns should produce a clear parse error naming the file and
  missing fields.

## Testing Strategy

Unit tests:

- API response parsing for h2h, spreads, and totals.
- Missing-market handling.
- Environment-variable configuration without exposing secrets.
- CSV folder discovery and idempotent import.
- Excel import when workbook support is installed.

Integration tests:

- Fixture-backed API client using local JSON payloads.
- `fetch-api-match` writes normalized records to SQLite.
- `analyze-live` combines fetched current odds with local historical data.
- Folder import handles a mixed directory of CSV, Excel, and unsupported files.

No tests should require a real API key or live network access. Live API behavior
can be covered by a manual smoke command documented in the README.

## Documentation

Update README with:

- API key setup through `ODDS_API_KEY`.
- Historical folder import examples.
- Live analysis examples.
- Explanation that current API odds may lack opening lines.
- A short warning that the tool does not place bets and does not guarantee
  outcomes.

## Implementation Boundary

This design should be implemented as one focused feature branch. It includes API
adapter scaffolding, fixture-backed tests, folder import, and CLI commands. It
does not include paid subscription management, browser automation, automated
betting, or a web UI.

