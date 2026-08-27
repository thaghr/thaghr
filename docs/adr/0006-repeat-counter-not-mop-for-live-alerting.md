# ADR 0006: Repeat-counter safeguard for live Phase 7 alerting; MOP stays an offline Phase 4 metric

**Status:** Accepted, 2026-08-01

## Context
Phase 7 needs a live signal that fires an alert when an agent is stuck in a failure loop, on top of the error-budget alert. Two candidates existed: MOP (sliding-window tool-call entropy, from the reliability literature) and a simple repeat-counter (abort/alert if the same `(tool, args)` pair repeats 3+ times within 6 steps, taken from the same paper's own methodology section).

MOP is the more sophisticated signal in principle, but its threshold calibration (θH, δ) is undocumented against ground truth; the source paper's own Table 15 sensitivity analysis is blank. Shipping an uncalibrated entropy threshold as a live alert risks either false positives that erode trust in the tool, or thresholds tuned to nothing.

## Decision
Live Phase 7 alerting uses the repeat-counter safeguard only, as a second Prometheus/Alertmanager rule alongside the error-budget alert. MOP is computed offline only, post-hoc from trajectory logs, alongside pass^k and GDS, as a Phase 4 metric, not a live alert.

## Consequences
- Ships a calibration-free, cheap, defensible live alert for Phase 7's DoD, instead of blocking on research that doesn't exist yet.
- MOP data still gets collected from real thaghr trajectories starting Phase 4, which is what would be needed to eventually calibrate it responsibly.
- MOP may be promoted to a live alert later, but only if it proves itself against that accumulated real trajectory data; this ADR is the record that promoting it earlier was considered and explicitly rejected for lack of evidence, not overlooked.
