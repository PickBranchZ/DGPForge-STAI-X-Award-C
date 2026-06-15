# Agent Run Summary

Mode: `from-paper`
Provider: `mock`
Validation status: `PASS`
Run requested: `True`

## Input
```text
examples\paper_excerpt_causal_ate.txt

We conducted a simple Monte Carlo study with 80 replications and sample size n = 600.
The goal was to estimate the marginal average treatment effect for a binary treatment A.
Covariates were generated as X1 ~ Normal(0, 1), X2 ~ Bernoulli(0.4), and X3 ~ Normal(0, 1).
Treatment followed logit P(A = 1 | X) = -0.2 + 0.8*X1 + 0.6*X2.
The outcome mean was linear: outcome = 2.0*A + 1.0*X1 + 0.5*X2 + 0.5*X3.
The treatment effect was 2.0. The residual variance was not reported.
```

## Artifacts
- Draft config: `draft_dgp.yaml`
- Assumptions log: `assumptions_log.md`
- Unresolved questions: `unresolved_questions.md`
- Validation report: `validation_report.md`
- Deterministic report: `report.html`

## Safeguard
The provider drafted structured contract fields only. DGPForge validation, truth engines, Monte Carlo runners, diagnostics, and reports produce the statistical evidence.
