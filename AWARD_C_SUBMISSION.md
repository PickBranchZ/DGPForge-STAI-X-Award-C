# [Award C] DGPForge - A Dual-Mode Causal DGP Simulation Agent for Known-Truth Estimator Stress-Testing

## Team Info

| Legal name | Affiliation | Institutional email | Kaggle username |
| --- | --- | --- | --- |
| Longfei Zhang | University of North Carolina at Chapel Hill | longfeiz@unc.edu | longfeiz |
| Yin Liu | University of North Carolina at Chapel Hill | liuyinxd@gmail.com | maeveliu |
| Shiyi Yang | University of North Carolina at Chapel Hill | shiyi@unc.edu | shiyiiii |

**Registered team name:** BiosForce

## What It Does

DGPForge is a reusable statistical agent module for causal simulation studies. It turns a causal DGP contract, or an optional LLM-assisted draft, into potential outcomes, known causal estimands, Monte Carlo estimator benchmarks, and diagnostic reports. The LLM may draft or review contracts, but deterministic modules generate all statistical evidence.

## Why Causal Simulation?

Observed-data agents can diagnose missingness, validation risk, or test choice, but they cannot know the true data-generating mechanism. DGPForge creates known-truth causal worlds where estimators and diagnostics can be stress-tested under controlled confounding, weak overlap, heterogeneity, missingness, clustering, and latent-U sensitivity.

## Demo Links

- Repository: https://github.com/PickBranchZ/DGPForge-STAI-X-Award-C
- Static gallery: https://pickbranchz.github.io/DGPForge-STAI-X-Award-C/
- Local fallback: `examples/generated_reports/index.html`

Static artifacts included in the repository:

- `examples/generated_reports/index.html`
- `examples/generated_reports/evaluation.html`
- `examples/generated_reports/assets/report_preview.png`
- `examples/generated_reports/assets/architecture.svg`

## Hero Demos

- LLM draft -> causal DGP contract -> validated report.
- Observed confounding / AIPW recovery of marginal ATE.
- Public-health count/rate causal estimands with exposure offset.
- Missingness mechanism stress test as a causal-data complication.

## Why This Is An Agent, Not Just A Script

DGPForge is agentic because it drafts or accepts a causal DGP contract, validates assumptions before execution, computes known causal truth, runs estimators under Monte Carlo, observes overlap, missingness, ICC, overdispersion, unsupported intervals, and calibration error, then responds with reproducible reports and safeguards.

## Architecture

| Award C Component | DGPForge Implementation |
| --- | --- |
| Brain/LLM | Optional LLM-assisted commands draft or review causal DGP contracts from natural language, paper-style excerpts, or existing YAML. The deterministic mock provider makes demos reproducible without API keys. |
| Memory | YAML contracts, generated reports, assumptions logs, CSV outputs, benchmark results, plots, `contract.yaml`, and `reproduce.md`. |
| Planning | The validated causal contract maps to sample sizes, replications, truth calculation, estimator set, diagnostics, and report generation. |
| Action | CLI commands and `scripts/build_demo.py` run simulations, estimators, diagnostics, reports, gallery generation, and the mini benchmark. |
| Observation | Bias, RMSE, Monte Carlo standard errors, attempted/valid run counts, coverage, treatment prevalence, overlap, missingness, ICC, overdispersion, calibration error, and warnings. |
| Response | Static HTML reports, demo gallery, preview image, reproducibility commands, assumptions logs, validation reports, and review artifacts. |

## Reproducibility

Requires Python 3.10 or newer.

```bash
python -m pip install -e ".[dev]"
python -m pytest
python benchmark/run_benchmark.py
python scripts/build_demo.py
python scripts/verify_demo.py --check
python -m py_compile streamlit_app.py
```

Each generated report folder includes `report.html`, `contract.yaml`, `reproduce.md`, estimator summaries, Monte Carlo CSVs, diagnostics, and plot artifacts.

## What Others Can Adopt

- The causal DGP contract pattern.
- The separation between proposal and deterministic evidence.
- Known-truth causal simulation reports for estimator stress tests.
- Assumption logs for underspecified text extraction.
- Reproducible static report folders with `contract.yaml` and `reproduce.md`.
- Honest uncertainty behavior: unsupported SE/CI/coverage stays blank.

## Scope And Safeguards

DGPForge uses only synthetic data generated from explicit causal DGP contracts; it includes no official STAI-X data and no external real datasets. It does not perform causal discovery, arbitrary DAG identification, do-calculus, or proof of real-world causal validity. The curated parser and optional LLM-assisted `from-paper` mode are not general paper-reproduction systems. Reports show SE/CI/coverage only when a valid approximation is implemented, leaving unsupported uncertainty blank rather than filling it with misleading numbers. In LLM-assisted mode, the model may draft, extract, explain, or review contracts, but deterministic checks under the configured DGP define what is verified.

This is a causal-structure-aware simulation workbench, not a real-data inference engine and not a formal proof of all estimator validity.
