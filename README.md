# Handicap AI

Local football handicap analysis tool.

## Setup

```bash
python -m pip install -e ".[dev]"
```

Use the bundled Codex Python in this workspace when the standard `python`
command points to the Windows Store alias.

## Test

```bash
python -m pytest
```

## MVP Flow

1. Import free-source odds data.
2. Resolve a match from home and away team names.
3. Output picks for Asian handicap, over/under, and 1X2.
