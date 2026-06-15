# DGPForge Mini Benchmark Results

These checks are small seeded smoke benchmarks for the Award C demo. They are intended to support the statistical story, not to provide exact numerical guarantees.

| Check | Status | Detail |
| --- | --- | --- |
| randomized naive approximately unbiased | PASS | \|bias\|=0.013 |
| observed confounding biases naive estimator | PASS | \|bias\|=0.729 |
| adjusted OLS close to known ATE | PASS | \|bias\|=0.025 |
| AIPW close to known ATE | PASS | \|bias\|=0.027 |
| Monte Carlo precision columns present | PASS | failure_rate, mcse_bias, mcse_coverage, mcse_rmse, n_attempted, n_valid |
| summary keeps attempted denominator | PASS | min attempted=30 |
| heterogeneous-effect true ATE is analytical | PASS | truth=2.200 |
| weak overlap warning triggered | PASS | propensity 1st percentile is below 0.05; propensity 99th percentile is above 0.95. |
| AIPW main variant close in DR demo | PASS | \|bias\|=0.000 |
| one-correct AIPW variants beat double-misspecified variant | PASS | ps_wrong=0.002, outcome_wrong=0.001, double_wrong=1.264 |
| coverage MCSE is finite | PASS | mcse_coverage=0.031 |
| binary truth has finite marginal risks and ratios | PASS | EY1=0.501, EY0=0.332, RD=0.169 |
| binary AIPW risk difference close to known RD | PASS | \|bias\|=0.006 |
| binary summary includes MCSE columns | PASS | failure_rate, mcse_bias, mcse_coverage, mcse_rmse, n_attempted, n_valid |
| report generation works | PASS | temporary report rendered |
| binary outcome report generation works | PASS | temporary binary report rendered |
| count/rate truth finite | PASS | rate0=0.0040, RD=0.0017 |
| count/rate offset g-comp close to known rate difference | PASS | \|bias\|=0.00002 |
| count/rate report generation works | PASS | temporary count/rate report rendered |
| missingness rate achieved | PASS | missing_rate=0.251 |
| missing data preserves full-data truth | PASS | Y_full exists and observed Y is masked |
| missing data report generation works | PASS | temporary missing-data report rendered |
| cluster-robust estimator runs | PASS | naive_se=0.049, cluster_se=0.054 |
| cluster diagnostics include ICC | PASS | empirical_icc=0.225 |
| clustered ICC report generation works | PASS | temporary clustered report rendered |
| calibration target checks pass | PASS | treatment and binary prevalence targets within tolerance |
| calibration writes report and calibrated DGP | PASS | calibration_report.html, calibrated_dgp.yaml |
| scenario grid writes combined artifacts | PASS | report.html, scenario_summary.csv, grid_results.csv |
| zero-U sensitivity cell has small adjusted bias | PASS | aipw_bias=-0.009 |
| strong latent U increases observed-estimator bias | PASS | low=-0.009, high=0.218 |
| sensitivity grid writes combined artifacts | PASS | report.html, sensitivity_summary.csv, sensitivity_grid.csv |

Interpretation:

- Randomized treatment should make the naive estimator approximately unbiased.
- Observed confounding should bias the naive estimator.
- Adjusted OLS and AIPW should move closer to the known ATE in this simple linear DGP.
- Heterogeneous-effect examples should report the analytical marginal ATE.
- MCSE columns make finite Monte Carlo precision visible.
- The double-robustness demo should show one-correct AIPW variants outperforming the double-misspecified variant in the seeded DGP.
- Binary-outcome reports should expose marginal risks and risk-difference benchmarks.
- Binary AIPW should recover the known marginal risk difference in the seeded demo.
- Unmeasured-confounding sensitivity should show larger observed-estimator bias when latent U affects both treatment and outcome.
- Count/rate outcomes should expose finite rate truth and offset-model benchmark checks.
- Missing-data mechanisms should preserve full-data truth while masking observed outcomes.
- Clustered data should report ICC diagnostics and cluster-aware SEs.
- Calibration should write a calibrated DGP and target-vs-achieved summary.
- Scenario-grid generation should produce combined CSV and HTML artifacts.
- Sensitivity-grid generation should produce combined CSV and HTML artifacts.
- Weak overlap should trigger a positivity warning.
- Report generation should complete without relying on external datasets.
