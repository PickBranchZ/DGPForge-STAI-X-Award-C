# Evaluation

Known-truth causal DGP simulation for estimator stress-testing.

This evaluation checks that the submitted artifact is rebuildable, internally consistent, and honest about statistical scope. DGPForge evaluates estimators under known causal truth generated from the configured DGP. This is simulation validation, not real-world causal identification. It does not use official STAI-X data or any external real dataset.

## What the automated tests cover

`python -m pytest` covers the deterministic contract-to-report loop used by the demo gallery:

- schema validation and YAML contract loading/saving;
- contract rejection for unsupported estimator/template combinations;
- deterministic simulation reproducibility under fixed seeds;
- known causal truth engines for continuous, binary, and count/rate outcomes;
- estimator execution and Monte Carlo summary fields;
- estimator failure observability, including status and error messages;
- bias, RMSE, MCSE, coverage, and attempted/valid denominator columns;
- positivity and overlap diagnostics;
- binary-outcome warnings and marginal risk reporting;
- count/rate exposure and overdispersion diagnostics;
- missing-data mechanism handling and full-data truth preservation;
- clustered ICC diagnostics and cluster-robust estimator execution;
- calibration target checks and calibrated-DGP artifacts;
- scenario-grid expansion and combined report generation;
- unmeasured-confounding sensitivity grid generation;
- optional mock LLM draft, extraction, and review workflows;
- context-specific report caveats for unsupported uncertainty;
- static gallery hero-card ordering and required links;
- generated-report manifest integrity checks.

These tests are regression checks for implemented workflows. They are not exhaustive over every possible DGP, sample size, estimator, or finite-sample edge case.

## What the benchmark verifies

`python benchmark/run_benchmark.py` runs a compact seeded benchmark over representative scenarios. It checks that:

- randomized treatment makes the naive difference approximately unbiased in the smoke setting;
- observed confounding biases the naive estimator;
- adjusted OLS and AIPW move closer to known truth in compatible linear DGPs;
- weak overlap triggers positivity warnings;
- heterogeneous-effect truth is computed as the configured marginal target;
- double-robustness variants show the intended one-correct vs double-misspecified pattern in the seeded DGP;
- binary-outcome truth exposes marginal risks, risk difference, risk ratio, and marginal odds ratio;
- count/rate truth and exposure-offset report generation work;
- missingness preserves full-data truth while masking observed outcomes;
- clustered ICC diagnostics and cluster-robust estimator execution work;
- calibration writes requested-vs-achieved target checks;
- scenario-grid and sensitivity-grid artifacts are generated;
- report caveats remain attached to relevant modules;
- generated report files can be checked by the static manifest.

The benchmark is deliberately small. It is meant to catch story-breaking regressions in the artifact pipeline, not to prove all statistical properties.

## What the hero reports demonstrate

The static gallery opens with four high-signal reports:

- LLM draft -> causal DGP contract -> validated report: the agent can propose a causal contract, log assumptions, validate the schema, and hand execution to deterministic modules.
- Observed confounding / AIPW recovery: treatment depends on prognostic covariates, so naive estimation is biased while adjusted and AIPW estimators move toward the marginal ATE.
- Count/rate causal estimands: event counts use exposure denominators, and uncertainty is shown only where a valid approximation is implemented.
- Missingness as causal-data complication: MCAR/MAR/MNAR are configured mechanisms, full-data truth remains the benchmark, and MNAR is not claimed to be solved by default.

The gallery then places all other seeded reports under More examples.

## What this does not prove

DGPForge reports known-truth simulation evidence under configured DGPs. That scope has explicit limits:

- It is not real-data inference.
- It is not causal discovery.
- It does not identify arbitrary DAGs or run do-calculus.
- It does not diagnose an observed external dataset.
- It does not infer confounding, missingness, clustering, or calibration from real data.
- It is not a formal proof of estimator validity.
- It is not a universal guarantee of unbiasedness or coverage.
- It does not claim all estimators are valid outside the configured DGP.
- It does not claim the curated parser can reproduce arbitrary papers.
- It does not use official STAI-X data or external real datasets.
- It does not fill unsupported SE, CI, or coverage values with placeholder uncertainty.
- It does not let LLM output override deterministic truth engines, estimators, diagnostics, or reports.

The intended interpretation is narrower and more useful: each passing check says the submitted artifact can be rebuilt, its contracts validate, and its seeded DGP stories remain internally consistent.

## How to reproduce

Run the validation sequence from the repository root:

```bash
python -m pip install -e ".[dev]"
python -m pytest
python benchmark/run_benchmark.py
python scripts/build_demo.py
python scripts/verify_demo.py --check
python -m py_compile streamlit_app.py
```

For stricter local development checks, also run:

```bash
python -m ruff check .
python -m black --check .
python -m mypy dgpforge
```

`python scripts/build_demo.py` refreshes the curated static reports, `evaluation.html`, and `manifest.json`. `python scripts/verify_demo.py --check` verifies committed generated-report paths, SHA-256 hashes, and file sizes.
