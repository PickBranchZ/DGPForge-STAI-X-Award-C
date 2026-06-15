# Agent Run Summary

Mode: `draft`
Provider: `mock`
Validation status: `PASS`
Run requested: `True`

## Input
```text
Create a simulation with binary treatment, continuous outcome, moderate confounding, heterogeneous treatment effect by X1, 500 units, 30 replications, and compare naive, IPW, and AIPW.
```

## Artifacts
- Draft config: `draft_dgp.yaml`
- Assumptions log: `assumptions_log.md`
- Unresolved questions: `unresolved_questions.md`
- Validation report: `validation_report.md`
- Deterministic report: `report.html`

## Safeguard
The provider drafted structured contract fields only. DGPForge validation, truth engines, Monte Carlo runners, diagnostics, and reports produce the statistical evidence.
