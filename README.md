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

## Source Boundaries

The tool uses conservative, best-effort, user-triggered source discovery,
fetching, and saved HTML parsing. It does not bypass login walls, paywalls,
CAPTCHA, anti-bot protections, or access controls. It does not place bets and
does not claim certainty.
