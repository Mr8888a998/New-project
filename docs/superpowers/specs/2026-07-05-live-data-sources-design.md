# Web Scraping and Hybrid UI Design

## Goal

Extend Handicap AI from a CLI MVP into a local odds-analysis workspace where the
user enters only the home and away team names, then the system can gather odds
from BetExplorer/OddsPortal-style pages, combine them with historical CSV/Excel
data, and output the best available picks for:

- Asian handicap or handicap-style spread.
- Over/under.
- 1X2.

The product remains a decision-support tool. It should expose data quality,
source coverage, and no-bet reasons instead of claiming certainty.

## Approved Product Direction

The next version should prioritize:

1. Web scraping from BetExplorer/OddsPortal-style odds pages.
2. Historical CSV/Excel imports for local training and similarity samples.
3. A local browser UI using an A+B hybrid layout:
   - Dashboard for the normal fast workflow.
   - Confirmation wizard only when match or odds extraction is ambiguous.

API adapters remain useful as later fallback sources, but they are not the main
implementation target for this phase.

## Scraping Boundaries

Scraping must be conservative and user-triggered.

The system should:

- Fetch pages only when the user requests an analysis or source refresh.
- Cache fetched HTML and parsed odds snapshots.
- Avoid high-frequency polling.
- Respect robots, terms, rate limits, and source failures.
- Never bypass login walls, paywalls, CAPTCHA, anti-bot protections, or access
  controls.
- Support manual import from saved HTML or CSV when a site blocks automated
  fetching.

This means live scraping is best-effort. The stable test contract is fixture
HTML stored in the repository, not live network behavior.

## Source Adapters

Add a web-source adapter layer above the existing normalized models.

Each adapter should expose:

```text
search_match(home_team, away_team, date_window) -> candidate matches
fetch_match_page(candidate or URL) -> raw HTML/cache record
parse_match_page(raw HTML) -> NormalizedMatchBundle
explain_coverage(bundle) -> markets found, missing markets, warnings
```

Initial adapter targets:

- BetExplorer-style pages as the first concrete adapter.
- OddsPortal-style pages as a second adapter when page access is stable enough.
- Saved HTML adapter for fixtures and blocked-site fallback.

All adapters must normalize into the existing domain records:

- `MatchRecord`
- `AsianHandicapLineRecord`
- `TotalsLineRecord`
- `OneXTwoLineRecord`
- `NormalizedMatchBundle`

Source-specific selectors and parsing rules should stay inside adapter modules.
The recommendation engine should not know which website produced the data.

## Data Storage

Keep SQLite as the local store and add scrape-focused metadata.

New or extended concepts:

- `source_fetches`: source name, URL, fetched_at, status code, cache path,
  content hash, error message.
- `scrape_jobs`: requested home/away, selected source, status, warnings.
- Parsed odds snapshots should keep source and bookmaker fields.
- Cached HTML files should live under ignored local data/cache paths, not in git.

Idempotency is required. Re-fetching the same match should update or add a new
snapshot without duplicating identical rows.

## Historical Imports

Continue supporting the existing Football-Data CSV import and add folder import.

Supported historical inputs:

- Football-Data CSV files.
- Football-Data-style Excel files when workbook parsing is available.
- A normalized user CSV template for custom datasets.

The folder importer should summarize imported files, skipped files, parse
errors, and match counts. One bad file should not abort the whole folder.

## Local UI

Build a local browser UI, not a landing page.

Recommended stack:

- Python backend using the existing package.
- FastAPI or a similarly small local web server.
- Server-rendered HTML templates plus small vanilla JavaScript for source
  refresh and wizard interactions.
- SQLite remains the data store.

The first screen is the analyst workspace.

Dashboard layout:

- Left rail: home team, away team, optional date, source checkboxes, analyze
  button, refresh source button.
- Top result strip: handicap pick, total pick, 1X2 pick, confidence and data
  quality.
- Middle panel: opening/current line movement and water/price movement.
- Source panel: BetExplorer/OddsPortal fetch status, parsed markets, warnings.
- Bottom panel: similar historical matches and risk tags.

Wizard triggers:

- Multiple candidate matches found.
- No exact team match but fuzzy candidates exist.
- Scraped table lacks one or more markets.
- BetExplorer and OddsPortal disagree materially.
- Extracted odds look incomplete or malformed.

Wizard steps:

1. Confirm matched event.
2. Review parsed markets.
3. Confirm source priority when sources conflict.
4. Run final analysis.

## User Workflow

Normal path:

```text
Open local UI
Enter England / Panama
Select BetExplorer and/or OddsPortal
Click Analyze
Review three market picks and source warnings
```

Ambiguous path:

```text
Enter team names
System finds several possible matches
Wizard asks user to pick the correct match
System parses odds tables
Wizard highlights missing or suspicious markets
User confirms
System outputs final picks
```

CLI should remain available for repeatable workflows:

```text
handicap-ai import-history-folder --db data/handicap_ai.sqlite --path data/history
handicap-ai scrape-match --db data/handicap_ai.sqlite --home England --away Panama --source betexplorer
handicap-ai ui --db data/handicap_ai.sqlite
```

## Recommendation Behavior

The recommendation engine should still produce one result per market:

- Handicap pick.
- Total pick.
- 1X2 pick.

Market-specific no-bet rules:

- Missing current market means no-bet for that market.
- Missing opening line lowers data quality but does not automatically block a
  pick if current line and historical samples are strong.
- Source conflict lowers confidence and triggers wizard confirmation.
- If only 1X2 is available, handicap and total should not infer picks from 1X2
  alone.

Risk tags to add or reuse:

- `scrape_match_ambiguous`
- `scrape_source_blocked`
- `scrape_market_missing`
- `scrape_table_untrusted`
- `source_conflict`
- `missing_opening_line`
- `historical_sample_small`
- `manual_confirmation_required`

## Error Handling

Source fetch failures:

- Show which source failed and why.
- Keep existing cached data when available.
- Mark cached data age in the UI.
- Do not overwrite newer good data with failed or malformed fetches.

Parsing failures:

- Store the raw fetch record for debugging.
- Show the missing selector or expected table type.
- Continue with other sources when possible.

UI failures:

- The UI should surface backend errors as plain status panels.
- No spinner should run forever; every job ends as success, partial, failed, or
  needs confirmation.

## Testing Strategy

No automated tests should depend on live BetExplorer or OddsPortal access.

Unit tests:

- Parse fixture HTML for 1X2, handicap, and over/under tables.
- Handle missing market tables.
- Handle multiple candidate matches.
- Normalize team names from source display strings.
- Summarize source coverage and warnings.

Integration tests:

- Saved HTML fixture imports into SQLite.
- `scrape-match` ingests one fixture-backed match.
- UI route renders the dashboard.
- UI analysis endpoint returns three market recommendations or market-specific
  no-bet responses.
- Folder import handles mixed CSV/Excel/unsupported files.

Manual smoke tests:

- Run local UI.
- Try a real BetExplorer/OddsPortal URL if accessible.
- Verify blocked or malformed pages produce clear warnings.

## Documentation

Update README with:

- Local UI startup command.
- Historical folder import examples.
- Saved HTML import fallback.
- Source limitations and scraping boundaries.
- Explanation that the tool does not place bets and does not guarantee results.

## Implementation Boundary

This phase should deliver a usable local UI, fixture-backed web-source parsing,
source-cache plumbing, and CLI/UI workflows. It should not attempt background
polling, account login, CAPTCHA solving, paid data access, browser extension
automation, or automated betting.

