# Assumptions Log

Provider: `mock`
Mode: `from-paper`

LLM-assisted mode drafts or reviews contracts only. Deterministic DGPForge modules produce truth, simulations, estimator summaries, diagnostics, and reports.

## Filled Or Inferred Fields
- `outcome.noise_sd` (defaulted): `1.0` - Residual variance was not specified; mock provider used a documented default.
- `n_replications` (defaulted): `30` - Monte Carlo replications were set to a small deterministic demo value.
- `treatment.formula.intercept` (defaulted): `-0.2` - Treatment intercept was not fully specified in the excerpt.
- `n_replications` (defaulted): `30` - Replications were defaulted for a fast reproducible mock demo.

## Confidence
medium
