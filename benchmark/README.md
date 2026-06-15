# DGPForge Mini Benchmark

Run from the repository root:

```bash
python benchmark/run_benchmark.py
```

The benchmark uses small seeded Monte Carlo runs to check the submission story:
randomized naive difference is approximately unbiased, observed confounding biases
the naive estimator, adjusted/AIPW estimators move closer to truth, heterogeneous
effect truth is analytical, MC precision columns are present, double-robustness
variants follow the seeded one-correct-vs-double-misspecified pattern, binary
outcome truth and AIPW risk-difference behavior are finite, count/rate truth and
exposure-offset reports work, missingness preserves full-data truth, clustered
ICC diagnostics and cluster-robust estimators run, calibration targets pass
within tolerance, weak overlap triggers a positivity warning, scenario-grid and
sensitivity-grid artifacts are written, latent U increases observed-estimator
bias in the sensitivity demo, and report generation works in a temporary folder.

Refresh the Markdown artifact:

```bash
python benchmark/run_benchmark.py --write-results
```
