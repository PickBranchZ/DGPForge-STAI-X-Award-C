# DGPForge Examples

These examples use only synthetic data generated from YAML DGP contracts.

## Scenarios

| File | Purpose | Expected statistical behavior |
| --- | --- | --- |
| `causal_ate_randomized.yaml` | Randomized binary treatment independent of covariates. | The naive difference in means should be approximately unbiased for the known ATE. |
| `causal_ate_observed_confounding.yaml` | Treatment depends on prognostic covariates `X1` and `X2`. | The naive estimator should be biased; adjusted OLS and AIPW should be closer to truth under this simple linear DGP. |
| `causal_ate_weak_overlap.yaml` | Strong treatment assignment dependence on covariates. | Positivity warnings should trigger; IPW can become unstable. |
| `causal_ate_heterogeneous_effect.yaml` | Treatment effect varies with binary modifier `X2`. | The marginal ATE is no longer just the baseline treatment effect; it equals the configured effect averaged over the covariate distribution. |
| `causal_ate_double_robustness.yaml` | AIPW variants omit role-driven nuisance features in the propensity model, outcome model, or both. | Under this seeded synthetic DGP and positivity, one-correct variants should be closer to truth than the double-misspecified variant. |
| `scenario_grid_causal_ate.yaml` | Expands the observed-confounding base contract across sample sizes, confounding strengths, and effect heterogeneity. | The combined report compares finite Monte Carlo evidence across grid cells; positivity pass/warning is not an overall validation grade. |
| `causal_binary_outcome.yaml` | Logistic binary-outcome DGP with marginal risk-difference benchmarking. | Reports `E[Y(1)]`, `E[Y(0)]`, risk difference, risk ratio, and marginal odds ratio; the logistic treatment coefficient is not the marginal causal target. |
| `causal_count_rate_outcome.yaml` | Public-health-style count outcome with an exposure denominator and Poisson offset model. | Reports known marginal rates, rate difference, rate ratio, exposure diagnostics, and `NA` SE/CI where intervals are not implemented. |
| `missing_data_mechanisms.yaml` | Continuous-outcome DGP with configured MAR outcome missingness. | Preserves `Y_full`, reports missingness rates and complete-case size, and compares complete-case with missingness-IPW behavior against full-data truth. |
| `clustered_ate_icc.yaml` | Continuous-outcome clustered DGP with target ICC and cluster-level confounding. | Compares adjusted OLS with naive vs cluster-robust SEs to show why cluster-aware uncertainty matters. |
| `calibration_targets.yaml` | Calibration config that loads a base DGP and targets treatment prevalence plus baseline outcome prevalence. | Writes a calibrated DGP and target-vs-achieved summary; calibration is approximate and uses only synthetic oracle checks. |
| `unmeasured_confounding_sensitivity.yaml` | Expands the binary-outcome DGP over latent `U` effects on treatment and outcome. | Bias heatmaps show how hidden-confounding strength changes observed-estimator bias under known truth. |
| `paper_excerpt_causal_ate.txt` | Curated text extraction demo. | The parser produces a DGP contract and assumptions log; it is not a general paper reproduction engine. |

## One-Click Gallery Build

```bash
python scripts/build_demo.py
```

Open `examples/generated_reports/index.html` after the build.

## Manual Commands

```bash
dgpforge run --config examples/causal_ate_randomized.yaml --out examples/generated_reports/randomized
dgpforge run --config examples/causal_ate_observed_confounding.yaml --out examples/generated_reports/observed_confounding
dgpforge run --config examples/causal_ate_weak_overlap.yaml --out examples/generated_reports/weak_overlap
dgpforge run --config examples/causal_ate_heterogeneous_effect.yaml --out examples/generated_reports/heterogeneous_effect
dgpforge run --config examples/causal_ate_double_robustness.yaml --out examples/generated_reports/double_robustness
dgpforge run --config examples/causal_binary_outcome.yaml --out examples/generated_reports/binary_outcome
dgpforge run --config examples/causal_count_rate_outcome.yaml --out examples/generated_reports/count_rate_outcome
dgpforge run --config examples/missing_data_mechanisms.yaml --out examples/generated_reports/missing_data
dgpforge run --config examples/clustered_ate_icc.yaml --out examples/generated_reports/clustered_icc
dgpforge calibrate --config examples/calibration_targets.yaml --out examples/generated_reports/calibration_demo
dgpforge grid --config examples/scenario_grid_causal_ate.yaml --out examples/generated_reports/scenario_grid
dgpforge sensitivity --config examples/unmeasured_confounding_sensitivity.yaml --out examples/generated_reports/unmeasured_confounding_sensitivity
dgpforge from-text --input examples/paper_excerpt_causal_ate.txt --out examples/generated_reports/from_text_demo
```
