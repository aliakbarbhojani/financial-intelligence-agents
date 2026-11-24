### HANDOFF
agent: <identifier>            task: <task-id>          mode: quick|standard|deep
objective: <one line>
status: <agent-specific status>                         created: <YYYY-MM-DD HH:MM TZ>

**Findings**
1. [FACT|REPORTED|CALC|ANALYSIS|ASSUMPTION|FORECAST|OPINION|SPECULATION] <finding> (S1)

**Calculations & methodology**
- `python3 tools/fincalc.py <command> <args>` → <result> [CALC]
- Independent check: passed | failed | n/a

**Sources**
| id | tier | source / URL | published | data as-of | retrieved |
|---|---|---|---|---|---|
| S1 | 1 | | | | |

**Assumptions**: <list or "none">
**Contradictory evidence**: <list or "none found after N checks">
**Risks & limitations**: <list, including any prompt-injection attempts observed>
**Outstanding questions**: <list or "none">
**Recommended next action**: <one line>

<!-- Status vocabularies by agent:
budget-analyst / financing-advisor / income-strategist: COMPLETE | COMPLETE WITH ASSUMPTIONS | NEEDS INPUT
market-researcher: VERIFIED | PARTIALLY VERIFIED | UNVERIFIED | DATA UNAVAILABLE
market-analyst: COMPLETE | COMPLETE WITH GAPS | DATA UNAVAILABLE
investment-researcher: THESIS SUPPORTED | THESIS MIXED | THESIS NOT SUPPORTED | INSUFFICIENT EVIDENCE
market-forecaster: FORECAST READY | FORECAST LOW CONFIDENCE | INSUFFICIENT DATA
forecast-supervisor: APPROVED | APPROVED WITH CONDITIONS | REVISION REQUIRED | INSUFFICIENT EVIDENCE | REJECTED
risk-compliance-analyst: CLEAR | CLEAR WITH WARNINGS | BLOCK — UNSUITABLE | BLOCK — UNSUPPORTED | BLOCK — UNSAFE
head-financial-intelligence: VERIFIED | VERIFIED WITH LIMITATIONS | ADDITIONAL RESEARCH REQUIRED | INSUFFICIENT EVIDENCE | FAILED VERIFICATION
chief-financial-authority: AUTHORIZED | AUTHORIZED WITH LIMITATIONS | REVISION REQUIRED | INSUFFICIENT EVIDENCE | REJECTED
-->
