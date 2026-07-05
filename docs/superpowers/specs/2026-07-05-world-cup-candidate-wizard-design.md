# World Cup Candidate Wizard Design

## Purpose

Upgrade the current saved-HTML workflow into a local World Cup analyst workflow:
the user enters only home and away team names, the app validates those names
against a 2026 FIFA World Cup seed dataset, shows candidate fixtures for
confirmation, and then analyzes the selected saved HTML source to produce the
three picks already supported by Handicap AI:

- Asian handicap pick
- Total pick
- 1X2 pick

This is the next practical step toward the desired handicap AI workspace while
keeping the system stable and testable. Direct live search/scraping of
BetExplorer or OddsPortal remains a later phase because those sites can change
structure, block automation, or require user interaction.

## Source Data

The seed dataset is scoped to the 2026 FIFA World Cup group stage. It should be
checked into the repository as structured data, not manually inserted into a
local SQLite database. The current 2026 tournament has 48 teams in 12 groups of
4, with group-stage pages sourcing standings and fixtures from FIFA.

Reference pages:

- https://en.wikipedia.org/wiki/2026_FIFA_World_Cup
- https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_K
- https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_L

## Seeded Groups

Group A:
- Mexico
- South Africa
- South Korea
- Czech Republic

Group B:
- Canada
- Bosnia and Herzegovina
- Qatar
- Switzerland

Group C:
- Brazil
- Morocco
- Haiti
- Scotland

Group D:
- United States
- Paraguay
- Australia
- Turkey

Group E:
- Germany
- Curacao
- Ivory Coast
- Ecuador

Group F:
- Netherlands
- Japan
- Sweden
- Tunisia

Group G:
- Belgium
- Egypt
- Iran
- New Zealand

Group H:
- Spain
- Cape Verde
- Saudi Arabia
- Uruguay

Group I:
- France
- Senegal
- Iraq
- Norway

Group J:
- Argentina
- Algeria
- Austria
- Jordan

Group K:
- Colombia
- Portugal
- DR Congo
- Uzbekistan

Group L:
- England
- Croatia
- Ghana
- Panama

## Naming Rules

The seed should include aliases for common source-name differences:

- DR Congo: `Congo DR`, `Democratic Republic of the Congo`
- United States: `USA`, `USMNT`
- South Korea: `Korea Republic`, `Korea Rep`
- Ivory Coast: `Cote d'Ivoire`, `Cote d Ivoire`
- Curacao: `Curacao`
- Czech Republic: `Czechia`

Alias matching should reuse the existing `normalize_team_name` behavior where
possible, with a small source-specific alias map only when normalization cannot
resolve common names.

## User Workflow

The first screen should become a match-search workspace instead of a saved-HTML
path form.

1. User enters home team and away team.
2. System validates both names against World Cup teams.
3. System generates one or more local candidate fixtures:
   - exact group-stage fixture if both teams are in the same group
   - fallback candidate when the names are valid but no seeded group fixture
     exists, marked as `not_in_group_stage`
4. UI shows candidate cards with:
   - home team
   - away team
   - group
   - match date/time when available
   - source status: cached HTML available, saved HTML required, or unsupported
5. User confirms one candidate.
6. User either:
   - uses an already mapped saved HTML file, or
   - supplies a saved HTML path in the confirmation panel
7. System runs the existing `analyze_saved_html` workflow and renders picks.

## Data Model

Add a small tournament seed layer. This should not replace the existing odds
`matches` table because seeded fixtures may exist before odds HTML has been
parsed.

### New Tables

`tournament_teams`:

- `tournament`: text, for example `fifa_world_cup`
- `season`: text, for example `2026`
- `group_name`: text, for example `K`
- `team_name`: canonical display name
- `normalized_name`: normalized lookup name
- `country`: optional country or association display name

Unique key: `(tournament, season, normalized_name)`.

`tournament_fixtures`:

- `fixture_id`: primary key
- `tournament`: text
- `season`: text
- `group_name`: text
- `home_team`: canonical display name
- `away_team`: canonical display name
- `home_normalized`: normalized home team lookup name
- `away_normalized`: normalized away team lookup name
- `kickoff_time`: nullable ISO timestamp
- `status`: `scheduled`, `finished`, or `unknown`

Unique key: `(tournament, season, home_normalized, away_normalized)`.

`fixture_source_links`:

- `fixture_id`
- `source`: `betexplorer`, `oddsportal`, or future source id
- `html_path`: nullable local saved HTML path
- `url`: nullable source URL for later live search support
- `status`: `available`, `missing`, or `stale`

This gives the UI a stable way to know whether it can analyze immediately or
needs a saved HTML path.

## Components

### Seed Module

Create `src/handicap_ai/world_cup_seed.py`.

Responsibilities:

- expose the 2026 World Cup groups and group-stage fixtures as dataclasses
- import the seed into SQLite
- avoid duplicate rows on repeated imports
- include aliases for lookup, but keep canonical display names stable

### Candidate Service

Create `src/handicap_ai/candidate_search.py`.

Responsibilities:

- resolve user-entered team names to seeded World Cup teams
- return candidate fixtures
- assign wizard status:
  - `ready`: exact fixture and saved HTML available
  - `needs_html`: exact fixture exists but no saved HTML path is mapped
  - `invalid_team`: one or both teams are unknown
  - `not_in_group_stage`: both teams are valid, but no group-stage fixture exists
- produce user-facing warnings and risk tags

### CLI

Add two small commands:

- `seed-world-cup --db data/handicap_ai.sqlite --season 2026`
- `find-candidates --db data/handicap_ai.sqlite --home England --away Ghana`

The CLI is useful for checking the seed and candidate behavior without opening
the browser.

### UI

Update the dashboard:

- make home and away team inputs editable
- add a "Find candidates" button
- show candidate confirmation cards
- keep saved HTML path as an advanced field inside the candidate panel
- keep the existing source selector and analysis result cards

The first usable path should be:

`England + Ghana -> candidate card -> confirm -> analyze saved HTML`

For fixture-backed tests, the candidate may map to the existing
`tests/fixtures/betexplorer_match.html` when the teams are England/Panama, and
tests can use a generated temporary mapping for other teams.

## Error Handling

- Unknown team names should return a clear API response, not a server error.
- Ambiguous aliases should return multiple team suggestions.
- Valid teams without a seeded fixture should show `not_in_group_stage`.
- Missing saved HTML should keep the user in the wizard and ask for a path.
- Parser failures should surface the existing source coverage warnings and add a
  wizard-level warning.

## Testing Strategy

Use TDD for each behavior.

Required tests:

- seed imports 48 World Cup teams
- seed imports the expected Group K and Group L teams
- repeated seed import is idempotent
- candidate search resolves exact names and common aliases
- candidate search finds Group K and Group L fixtures
- candidate search reports `invalid_team`
- candidate search reports `not_in_group_stage`
- CLI exposes `seed-world-cup` and `find-candidates`
- UI renders editable home and away team inputs
- UI candidate endpoint returns a candidate for England vs Ghana
- UI can analyze a confirmed candidate with a saved HTML path

Full test suite must remain green.

## Out Of Scope

This phase does not:

- bypass login, paywall, CAPTCHA, or anti-bot protection
- place bets
- claim certainty
- scrape live BetExplorer/OddsPortal search pages automatically
- download or store copyrighted full web pages in git

Live source search can be added later after the local candidate wizard is stable.

## Implementation Notes

- Use existing `Database`, `normalize_team_name`, `analyze_saved_html`, and UI
  patterns.
- Keep seeded data in source code or a small checked-in JSON/CSV file. Prefer a
  JSON file if the fixture list grows beyond what is comfortable in Python.
- Existing saved HTML fixture tests should continue to pass unchanged.
- The UI should remain an operational dashboard, not a marketing page.
