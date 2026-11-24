---
id: FJ-<YYYYMMDD>-<HHMM>-<slug>
record_type: TIME_SENSITIVE
created: <YYYY-MM-DD HH:MM TZ>
agent: market-forecaster
subject: <instrument / index / indicator>
exchange: <exchange or n/a>
horizon: <e.g. 3 months, ending YYYY-MM-DD>
review_date: <YYYY-MM-DD>
supervisor_status: <filled by orchestrator note in outcome file, never edited here>
---

<!-- IMMUTABLE ONCE WRITTEN. The finance-gate hook blocks edits and overwrites.
     Record outcomes in memory/forecast-journal/outcomes/OUT-<same id>.md -->

## Starting point (verified)
| Metric | Value | As of | Source |
|---|---|---|---|

## Benchmark model
<e.g. random walk: value unchanged at horizon; or historical drift X%/yr>

## Key assumptions
1.

## Scenarios
| Scenario | Range / outcome | Drivers | Likelihood (method or qualitative) |
|---|---|---|---|
| Bull | | | |
| Base | | | |
| Bear | | | |

## Confidence
<low | moderate | high> because …

## Invalidation conditions
-
