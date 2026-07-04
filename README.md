# Handicap AI

Local football handicap analysis tool.

## Setup

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

If the standard `python` command points to the Windows Store alias, use the
bundled Codex Python executable for local verification.

## Import Fixture Data

```bash
handicap-ai init-db --db data/handicap_ai.sqlite
handicap-ai import-football-data --db data/handicap_ai.sqlite --csv tests/fixtures/football_data_sample.csv --season 2026
```

## Analyze a Match

```bash
handicap-ai analyze --db data/handicap_ai.sqlite --home England --away Panama
```

The output includes:

- Handicap pick
- Total pick
- 1X2 pick
- Confidence
- Data quality
- Reasons
- Risk tags

## Notes

The MVP is a decision-support tool. It does not place bets and does not claim
certainty.
