# Methodology and calculation contract

## Purpose

The application implements the conventional DCMA 14-Point Schedule Assessment as a diagnostic screen. A metric is never silently marked compliant when its required inputs are missing.

## Status model

- **Cumple:** calculation is available and meets the threshold.
- **No cumple:** calculation is available and breaches the threshold.
- **Revisar:** a provisional proxy was required, such as `last_recalc_date` in place of an authoritative Data Date.
- **No evaluable:** the required baseline, milestone selection or controlled P6 test has not been supplied.

## Metric contract

| # | Metric | Calculation | Threshold |
|---|---|---|---|
| 1 | Missing Logic | Incomplete non-milestones without predecessor and/or successor / incomplete non-milestones | ≤5% |
| 2 | Leads | Negative-lag relationships / all relationships | 0% |
| 3 | Lags | Positive-lag relationships / all relationships | ≤5% |
| 4 | Relationship Types | Non-FS relationships / all relationships | ≤10% |
| 5 | Hard Constraints | Incomplete tasks with Mandatory Start/Finish or Start/Finish On / incomplete tasks | ≤5% |
| 6 | High Float | Incomplete tasks with Total Float >352 h / incomplete tasks | ≤5% |
| 7 | Negative Float | Incomplete tasks with Total Float <0 / incomplete tasks | 0% |
| 8 | High Duration | Incomplete non-milestones with Remaining Duration >352 h / incomplete non-milestones | ≤5% |
| 9 | Invalid Dates | Actual dates after Data Date or forecast dates before Data Date | 0% |
| 10 | Resources | Incomplete non-milestones without assignments / incomplete non-milestones | 0% |
| 11 | Missed Tasks | Tasks whose actual/forecast finish exceeds baseline finish / comparable baseline tasks | ≤5% |
| 12 | Critical Path Test | Add 600 days to a critical activity in controlled P6 copy and verify equivalent project-finish movement | Equivalent response |
| 13 | CPLI | (Critical Path Length + Total Float) / Critical Path Length | ≥0.95 |
| 14 | BEI | Tasks actually complete by Data Date / baseline tasks planned complete by Data Date | ≥0.95 |

The 44-day tests are converted using the conventional 8-hour day: `44 × 8 = 352 h`. A later version will make this threshold calendar-aware while preserving the published DCMA comparison.

## Controlled limitations

1. The Critical Path Test is not inferred from static XER data because it is a dynamic scheduling test.
2. CPLI remains unavailable until the contractual completion milestone and calendar basis are selected.
3. BEI and Missed Tasks require both an authoritative Data Date and an approved baseline.
4. Dummy assignments satisfy the presence of a resource record but do not prove capacity, trade, crew or equipment feasibility.

## Adjacent management frameworks

- [DCMA EVMS Compliance Metrics](https://www.dcma.mil/Portals/31/Documents/HQ/EVMS/DCMA%20EVMS%20Compliance%20Metrics%20v7.0%2020250115.xlsx)
- [PMI Practice Standard for Scheduling - Third Edition](https://www.pmi.org/standards/scheduling-third-edition)
- [AACE International Recommended Practices](https://web.aacei.org/resources/recommended-practices)

