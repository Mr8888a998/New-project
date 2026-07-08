# Handicap AI

Local football handicap analysis tool.

## Setup

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

If the standard `python` command points to the Windows Store alias, use the
bundled Codex Python executable for local verification.

## Import Historical Data

```bash
handicap-ai init-db --db data/handicap_ai.sqlite
handicap-ai import-football-data --db data/handicap_ai.sqlite --csv tests/fixtures/football_data_sample.csv --season 2026
handicap-ai import-history-folder --db data/handicap_ai.sqlite --path tests/fixtures/history_folder --season 2026
```

## Seed World Cup Candidates

```bash
handicap-ai seed-world-cup --db data/handicap_ai.sqlite --season 2026
handicap-ai find-candidates --db data/handicap_ai.sqlite --home England --away Ghana
```

The World Cup candidate workflow lets you enter home and away team names,
confirm a seeded group-stage fixture, then analyze a saved odds HTML file.

## Prepare Local Demo Data

Use this when the dashboard is empty and you want a usable local dataset in one
step:

```bash
handicap-ai prepare-demo-data --db data/handicap_ai.sqlite
```

This seeds the 2026 World Cup teams and fixtures, imports the bundled historical
sample data, and registers an available BetExplorer HTML page for England vs
Panama when the local fixture/cache file exists. In the dashboard, click
`Prepare demo data` to run the same workflow and refresh source readiness and
backtest panels.

## Discover and Cache Source HTML

```bash
handicap-ai discover-sources --db data/handicap_ai.sqlite --home England --away Ghana --source betexplorer
handicap-ai register-source-url --db data/handicap_ai.sqlite --home England --away Ghana --source betexplorer --url https://www.betexplorer.com/football/world/world-cup/england-ghana/example/
handicap-ai fetch-source-html --db data/handicap_ai.sqlite --home England --away Ghana --source betexplorer
```

Source discovery and fetching are user-triggered. If a site blocks automated
access, paste a manually saved HTML path in the dashboard and use the saved-HTML
analysis flow.

## Auto Analyze From UI

The dashboard can run the candidate workflow automatically after you enter home
and away teams. Click `Auto analyze` to check the seeded World Cup fixture,
reuse cached source HTML when available, or attempt source discovery and HTML
fetch for the selected source. If the source blocks automation or no URL is
found, the dashboard keeps the manual URL, fetch, and saved-HTML controls ready.

The v2 dashboard keeps the main input simple: enter the home team and away team,
choose a source, then run `Auto analyze`. The analysis result includes the best
available picks for:

- Handicap
- Total
- 1X2

The result panels also show opening/closing handicap, opening/closing total,
water movement, closing 1X2 prices, market-disagreement score, per-market
numeric score, recommendation reason, and risk tags.

## Source Status And Backtest

Use source status to see how many seeded World Cup fixtures already have
registered source links or cached HTML:

```bash
handicap-ai source-status --db data/handicap_ai.sqlite --source betexplorer
```

Use the source matrix and batch source checks to inspect BetExplorer and
OddsPortal coverage together, then see the next action for each fixture/source
cell:

```bash
handicap-ai source-matrix --db data/handicap_ai.sqlite
handicap-ai source-checks --db data/handicap_ai.sqlite --limit 20
handicap-ai source-checks --db data/handicap_ai.sqlite --action needs_fetch
```

Run a local historical backtest over finished matches already imported into the
database:

```bash
handicap-ai backtest --db data/handicap_ai.sqlite --limit 50
```

The backtest reports picks, hits, misses, no-bets, pushes, and hit rate for
handicap, total, and 1X2. By default it uses only earlier fixtures as comparison
history when kickoff times are available.

## Analyze Saved Odds HTML

```bash
handicap-ai scrape-match --db data/handicap_ai.sqlite --source betexplorer --html tests/fixtures/betexplorer_match.html
```

The saved-HTML flow is the stable fallback when a live odds site blocks
automated fetching or changes its page structure.

## Run Local UI

```bash
handicap-ai ui --db data/handicap_ai.sqlite --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`, enter home and away team names, and click
`Auto analyze` to run the candidate, source, fetch, and analysis flow. If a
source blocks automation, use the manual URL, fetch, or saved HTML controls.
Use the `Refresh source status` and `Run backtest` buttons to inspect data
readiness and historical performance inside the same workspace.

## Output

The output includes:

- Handicap pick
- Total pick
- 1X2 pick
- Confidence
- Data quality
- Reasons
- Risk tags
- Source coverage
- Feature panel
- Scorecard
- Source readiness
- Backtest summary

## Source Boundaries

The tool uses conservative, best-effort, user-triggered source discovery,
fetching, and saved HTML parsing. It does not bypass login walls, paywalls,
CAPTCHA, anti-bot protections, or access controls. It does not place bets and
does not claim certainty.
