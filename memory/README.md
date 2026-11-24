# Memory: controlled local knowledge base

A file-based memory, readable by every finance agent and writable only through narrow, hook-enforced paths. It improves **instructions, methods and retrievable knowledge**. It doesn't retrain or modify any AI model.

## Layout

| Path | Contents | Who writes | Git |
|---|---|---|---|
| `knowledge/` | Verified methodologies, source preferences, analytical lessons | **User** (agents may only *propose* changes) | committed |
| `error-log/` | One file per analytical error: cause, fix, prevention | head-financial-intelligence (new files only) | ignored |
| `forecast-journal/` | One immutable file per forecast | market-forecaster (new files only) | ignored |
| `forecast-journal/outcomes/` | Outcome evaluations linked to forecast IDs | head / user (new files only) | ignored |
| `research-cache/` | Verified, non-personal research with `revalidate_by` dates | orchestrator (after Chief authorisation) | ignored |
| `private/` | User-approved preferences only | **main session only, after explicit user approval** (hook denies agents) | ignored |

## Record types (every entry declares one)

| Type | Meaning | Reuse rule |
|---|---|---|
| `PERSISTENT_FACT` | Stable knowledge (formula definitions, structural facts) | Reuse; re-verify yearly |
| `TIME_SENSITIVE` | Prices, rates, news-driven claims | **Revalidate before reuse** once past `revalidate_by` |
| `USER_PREFERENCE` | e.g. preferred currency, report length | Only if user-approved; user can delete any time |
| `ANALYTICAL_LESSON` | Error-log and forecast-outcome lessons | Apply as checklist items |
| `UNVERIFIED_ASSUMPTION` | Working assumptions not yet confirmed | Never present as fact |

## Privacy rules
- No income, balances, debts, holdings or identity data is stored unless the user explicitly authorises it, and then only in `private/`.
- Never store credentials, account numbers or government ID numbers, even if asked.
- Deleting a file deletes the memory. There are no hidden copies.

## Integrity rules
- Forecast journal entries are **never** edited after creation, so accuracy can't be made to look better than it was. Outcomes go in separate files.
- Error-log entries are append-only. Follow-ups are new entries that reference the original ID.
- Agents can't change their own instructions, permissions or guardrails (`.claude/` is write-protected by the hook and requires user approval in the main session).
