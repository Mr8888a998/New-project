# Handicap AI Tool Design

## Goal

Build a football handicap analysis tool that lets the user enter only the home
team and away team, then automatically finds the relevant match, gathers free
odds/handicap data, and outputs the best pick for three markets:

- Asian handicap / underdog side
- Over/under
- 1X2

The first version is a decision-support tool, not a guaranteed prediction
engine. It should show the pick, confidence, similar historical cases, and risk
tags so the user can judge whether the recommendation is worth using.

## Scope

The system should support all competitions at the architecture level, but the
first implementation will start with a small number of free sources and expand
through source adapters.

Included in v1:

- Input by home team and away team only.
- Automatic match lookup for upcoming or recent matches.
- Free-source data ingestion through adapters.
- Normalized storage for matches, teams, odds snapshots, Asian handicap lines,
  total lines, 1X2 odds, and results.
- Feature engineering for opening line, closing line, line movement, water
  movement, movement speed, market disagreement, and similar-line retrieval.
- Three independent market recommendations.
- A no-bet option when the data quality or signal strength is too weak.

Out of scope for v1:

- Paid odds APIs.
- User account system.
- Automated betting.
- Claims of certainty.
- Full live in-play betting automation.
- Using political or conspiracy assumptions as model truth labels.

## User Experience

The user enters:

```text
Home: England
Away: Panama
```

If the system finds exactly one plausible match, it analyzes that match
directly. If it finds multiple matches, it asks the user to choose one by date
and competition. If it finds none, it reports which sources were searched and
why no match was resolved.

The primary output should be concise:

```text
Handicap pick: Panama +2.25
Total pick: Under 3.0
1X2 pick: England win

Confidence:
- Handicap: medium-high
- Total: medium
- 1X2: high

Risk tags:
- Favorite line moved too deep
- Opening-to-closing movement favors underdog value
- Recheck near kickoff
```

The expanded output should include:

- Current line and opening line.
- Water/price changes.
- Similar historical samples.
- Historical cover rates.
- Data source coverage.
- Reasons for each pick.
- No-bet rationale when applicable.

## Data Sources

The first version will use free sources only.

Recommended source strategy:

1. Football-Data CSV as the stable training and validation seed where available.
   It is structured and useful for historical odds, totals, Asian handicap
   fields, and results.
2. BetExplorer-style web scraping for broader match discovery and odds pages.
3. OddsPortal-style web scraping as an additional adapter if pages are accessible
   and stable enough.

Each source must be isolated behind an adapter:

```text
SourceAdapter
- search_match(home_team, away_team)
- fetch_match_metadata(match_id)
- fetch_odds_snapshots(match_id)
- fetch_result(match_id)
- normalize(raw_payload)
```

The analysis engine must consume only normalized records, never source-specific
HTML or CSV fields.

## Core Tables

### teams

- `team_id`
- `canonical_name`
- `country`
- `aliases`
- `source_ids`

### matches

- `match_id`
- `home_team_id`
- `away_team_id`
- `competition`
- `season`
- `kickoff_time`
- `status`
- `home_score`
- `away_score`
- `source_ids`

### odds_snapshots

- `snapshot_id`
- `match_id`
- `source`
- `bookmaker`
- `market_type`
- `captured_at`
- `is_opening`
- `is_closing`

### asian_handicap_lines

- `snapshot_id`
- `line`
- `home_price`
- `away_price`
- `favorite_side`

### totals_lines

- `snapshot_id`
- `total`
- `over_price`
- `under_price`

### one_x_two_lines

- `snapshot_id`
- `home_win_price`
- `draw_price`
- `away_win_price`

### match_result_labels

- `match_id`
- `result_1x2`
- `home_margin`
- `handicap_cover`
- `total_cover`
- `favorite_cover`

### derived_features

- `match_id`
- `open_handicap`
- `close_handicap`
- `handicap_delta`
- `open_total`
- `close_total`
- `total_delta`
- `home_water_delta`
- `away_water_delta`
- `over_water_delta`
- `under_water_delta`
- `movement_pattern`
- `movement_speed`
- `market_disagreement_score`
- `line_depth_score`
- `similarity_bucket`
- `data_quality_score`

## Feature Engineering

The model should transform raw odds into interpretable handicap features.

Line movement:

- Opening handicap to closing handicap.
- Opening total to closing total.
- Direction of movement: up, down, stable.
- Magnitude of movement in quarter-ball units.

Water/price movement:

- Favorite price change.
- Underdog price change.
- Over price change.
- Under price change.
- Whether line movement and water movement agree or diverge.

Pattern tags:

- Line up, favorite water down.
- Line up, favorite water up.
- Line down, underdog water down.
- Total up, over water stable.
- Total down, under water down.
- Stable handicap with moving totals.

Market disagreement:

- Asian handicap direction vs 1X2 implied probability.
- Total movement vs expected scoreline from 1X2.
- Favorite getting stronger in 1X2 while handicap becomes less favorable.

Historical similarity:

- Same opening handicap bucket.
- Same closing handicap bucket.
- Same total bucket.
- Similar water movement.
- Similar favorite strength.
- Same competition type when available.
- Same home/away role when available.

Chain comparison:

- A vs B historical line.
- B vs C historical line.
- A vs C inferred reasonable range.
- Current A vs C line compared with inferred range.

## Label System

Outcome labels:

- `result_1x2`: home win, draw, away win.
- `handicap_cover`: home cover, away cover, push, half win, half loss.
- `total_cover`: over, under, push, half over, half under.
- `favorite_cover`: favorite cover, favorite fail, push.

Recommendation labels:

- `best_handicap_pick`: home side, away side, no bet.
- `best_total_pick`: over, under, no bet.
- `best_1x2_pick`: home win, draw, away win, no bet.

Risk labels:

- `line_too_deep`
- `favorite_heat`
- `underdog_value`
- `total_trap_candidate`
- `market_disagreement`
- `late_move`
- `low_data_quality`
- `source_conflict`
- `no_clear_edge`

The risk labels are rule-based in v1. They should not be treated as proven
truth until enough historical validation exists.

## Recommendation Engine

The engine should combine two layers:

1. Rule-based interpretation.
2. Historical similarity scoring.

For each market, the engine computes:

- Candidate pick.
- Confidence score.
- Supporting sample size.
- Historical hit rate.
- Current line movement explanation.
- Risk tags.

The system then picks the best option for each market unless the confidence or
data quality is too low, in which case it outputs `no bet`.

Example handicap logic:

```text
If favorite opens -1.75, closes -2.25, favorite water does not strongly support
the deeper line, and similar historical cases show poor favorite cover rate,
recommend underdog +2.25 or no bet depending on confidence.
```

Example total logic:

```text
If total moves from 3.0 to 3.25 but over price rises or remains weak, and
similar cases show weak over conversion, recommend under.
```

Example 1X2 logic:

```text
If favorite handicap value is weak but 1X2 implied probability remains strong,
recommend favorite win rather than favorite handicap cover.
```

## Data Quality Rules

Every recommendation must include a data quality score.

Data quality is reduced when:

- Only one source has odds.
- Opening line is missing.
- Closing line is missing.
- Bookmaker fields disagree too strongly.
- Team matching is fuzzy.
- Result data is missing.
- Similar historical sample size is too small.

When data quality is below threshold, the affected market should output no bet.

## System Architecture

```text
CLI / Web UI
  -> Match Resolver
  -> Source Adapters
  -> Normalizer
  -> Local Database
  -> Feature Builder
  -> Similarity Search
  -> Recommendation Engine
  -> Report Renderer
```

Components:

- Match Resolver: maps home/away names to a specific upcoming or recent match.
- Source Adapters: scrape or download data from free sources.
- Normalizer: converts source-specific data to canonical records.
- Local Database: stores normalized history and latest snapshots.
- Feature Builder: computes engineered handicap features.
- Similarity Search: finds historical matches with comparable lines.
- Recommendation Engine: outputs best picks for handicap, total, and 1X2.
- Report Renderer: creates the user-facing explanation.

## Error Handling

If no match is found:

- Show the searched names.
- Show searched sources.
- Suggest adding date or competition as optional disambiguation.

If odds are incomplete:

- Analyze available markets only.
- Output no bet for missing markets.
- Show missing fields.

If sources conflict:

- Prefer more complete source data.
- Flag `source_conflict`.
- Lower confidence.

If scraping fails:

- Preserve cached data.
- Report stale timestamp.
- Avoid pretending the data is current.

## Testing Strategy

Unit tests:

- Team name normalization.
- Handicap and total cover calculations.
- Quarter-line settlement.
- Movement pattern classification.
- Recommendation rules.

Integration tests:

- Football-Data CSV import.
- One web source adapter with saved HTML fixtures.
- Match resolution from home/away names.
- End-to-end report generation from fixture data.

Validation tests:

- Backtest historical matches by hiding final results.
- Compare recommendations with actual cover labels.
- Report hit rate, sample size, and no-bet frequency by market.

## Open Assumptions

- Free sites may change layouts, so adapters must be easy to repair.
- Some sites may restrict scraping; the implementation should respect robots,
  rate limits, and avoid aggressive requests.
- The first version can use a local database such as SQLite.
- The first interface can be CLI first, then a web UI after the engine works.

## Approved Product Direction

The confirmed direction is:

- User enters only home and away team names.
- System automatically finds match and odds data from free sources.
- Architecture supports all competitions through source adapters.
- First sources are selected by the builder, with a generic adapter framework.
- Output must include best picks for handicap, over/under, and 1X2.
- No-bet is allowed when signal quality is too low.
