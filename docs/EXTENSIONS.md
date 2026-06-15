# Extension Roadmap

DGPForge is intentionally template-first. A new statistical template should define the estimand, truth engine, estimator set, diagnostics, report additions, and validation checks before it becomes part of the demo gallery.

## Current Flagship Scope

Cross-sectional binary-treatment continuous-outcome marginal ATE:

- Contract: covariates, binary treatment assignment, linear continuous outcome, sample sizes, replications, seed, estimators.
- Truth: analytical ATE for constant and supported linear heterogeneous treatment effects.
- Estimators: naive difference, adjusted OLS, IPW, AIPW, and role-driven nuisance misspecification variants for demonstration.
- Diagnostics: bias, RMSE, Monte Carlo standard errors, empirical SD, mean SE, coverage, attempted/valid run counts, treatment prevalence, propensity overlap, positivity warning.
- Scenario grid: expands a base contract over sample size, confounding strength, and treatment-effect heterogeneity, then writes combined HTML/CSV artifacts.
- Double-robustness demo: compares AIPW variants with correct or deliberately misspecified nuisance models in a seeded synthetic DGP under positivity.

Cross-sectional binary-treatment binary-outcome marginal risk estimands:

- Contract: logistic binary outcome, binary potential outcomes, marginal risk-difference primary target, optional risk-ratio and marginal odds-ratio truth reporting.
- Truth: deterministic oracle Monte Carlo from counterfactual probabilities `p1` and `p0`.
- Estimators: naive risk difference, logistic g-computation risk difference, IPW risk difference, AIPW risk difference, and optional oracle adjusted model including latent `U`.
- Diagnostics: outcome prevalence, oracle `E[Y(1)]`/`E[Y(0)]`, rare-outcome warnings, simple separation warnings, MCSE, and failure rates.
- Reporting: marginal-vs-conditional logistic note, risk-scale cards, and binary prevalence diagnostics.

Unmeasured-confounding sensitivity:

- Contract: optional latent normal `U` can affect treatment and outcome while remaining hidden from observed estimators.
- Runner: `dgpforge sensitivity` expands a grid over `U -> A` and `U -> Y` strengths.
- Reporting: bias heatmaps and combined CSV summaries under known truth.

Count/rate outcomes with exposure offsets:

- Contract: count outcome type, Poisson model, exposure distribution, optional negative-binomial overdispersion, and marginal rate estimands.
- Truth: oracle marginal rates `sum(mu_a) / sum(exposure)`, rate difference, rate ratio, log rate ratio, and mean counts.
- Estimators: naive rate difference, Poisson offset g-computation, and IPW rate difference.
- Diagnostics: exposure summaries, observed rate, count mean/variance, zero fraction, and overdispersion warnings.
- Reporting: public-health exposure-offset interpretation; naive rate difference has a simple Poisson rate SE when overdispersion is disabled, while unsupported count/rate intervals remain blank.

Missing data mechanisms:

- Contract: optional outcome missingness with MCAR, MAR, or MNAR mechanism, target missingness rate, formula terms, and observation indicators.
- Truth: remains the full-data estimand because missingness is applied after full potential outcomes are generated.
- Estimators: complete-case variants and a missingness-IPW adjusted OLS option for observed outcomes.
- Diagnostics: observed missingness rate, missingness by treatment, complete-case sample size, fraction dropped, and MNAR warning.
- Reporting: configured mechanism summary and caveat that MNAR is a synthetic stress test, not a solved identification problem.

Clustered or multilevel data with ICC:

- Contract: optional clusters, fixed cluster size, ICC, random intercepts, and optional cluster-level confounder.
- Truth: oracle simulation over the configured cluster-level effects, with individual-weighted estimands in the demo.
- Estimators: adjusted OLS with naive SE and adjusted OLS with manual CR1 cluster-robust sandwich SE over cluster score sums.
- Diagnostics: number of clusters, cluster-size summary, target/empirical ICC, cluster random-effect SD, and few-cluster warning.
- Reporting: coverage-focused interpretation showing why cluster-aware uncertainty matters, with explicit few-cluster warnings.

DGP calibration engine:

- Config: separate calibration YAML that loads a base DGP and specifies design targets, tolerances, oracle sample size, and seed.
- Targets: treatment prevalence, binary control outcome prevalence, count baseline rate, and continuous-outcome ICC.
- Outputs: `calibrated_dgp.yaml`, `calibration_summary.csv`, and `calibration_report.html`.
- Reporting: requested vs achieved targets, calibrated parameter values, pass/fail tolerances, and approximation caveat.

The current template identifiers are `cross_sectional_binary_treatment_continuous_outcome`, `cross_sectional_binary_treatment_binary_outcome`, and `cross_sectional_binary_treatment_count_outcome` in `dgpforge/schema.py`.

## Implemented And Future Extension Notes

### 1. Heterogeneous Treatment Effects

- Implemented now: one configured linear effect modifier, analytical marginal ATE, report cards, and a treatment-effect heterogeneity plot.
- Roadmap contract additions: richer effect modifiers, nonlinear interactions, subgroup labels.
- Roadmap truth engine: oracle Monte Carlo when the modifier distribution is complex.
- Roadmap estimators: subgroup contrasts, CATE learners, interaction-adjusted OLS.
- Roadmap diagnostics: subgroup bias/RMSE, calibration by modifier strata, overlap within subgroups.
- Roadmap reporting: subgroup or CATE plots beyond the current marginal-ATE report.

### 2. Binary Outcomes And Risk Estimands

- Implemented now: logistic binary outcome, oracle marginal risks, risk difference, risk ratio, marginal odds ratio, binary RD estimators, and risk-scale report cards.
- Roadmap contract additions: nonlinear effects, richer interactions, and alternative binary estimand scales as primary benchmark targets.
- Roadmap truth engine: exact integration when covariate distributions make it practical.
- Roadmap estimators: binary-outcome nuisance misspecification variants and richer bootstrap intervals.
- Roadmap diagnostics: calibration plots and event-rate plots beyond the current prevalence table.

### 3. Unmeasured-Confounding Sensitivity

- Implemented now: one latent normal `U`, hidden from observed estimators by default, with grid-based bias heatmaps.
- Roadmap contract additions: binary latent variables, nonnormal latent variables, and multiple hidden confounders.
- Roadmap estimators: formal sensitivity-analysis estimators rather than controlled DGP stress tests.
- Roadmap diagnostics: partial-R2-style summaries and richer graphical bias contours.

### 4. Count / Rate Outcomes With Exposure Offsets

- Implemented now: Poisson and Gamma-Poisson negative-binomial count DGPs, exposure denominators, marginal rate truth, three rate estimators, a simple naive Poisson rate SE when applicable, and report diagnostics.
- Roadmap contract additions: zero inflation, alternative exposure distributions, and explicit rate-ratio primary targets.
- Roadmap estimators: robust offset-model SEs, negative-binomial g-computation, AIPW rate estimators, and bootstrap intervals.
- Roadmap reporting: richer event-rate plots and standardized rate displays across subgroups.

### 5. Missing Data Mechanisms

- Implemented now: outcome MCAR/MAR/MNAR mechanisms, `Y_full`, `R_Y`, complete-case estimators, and missingness-IPW adjusted OLS.
- Roadmap contract additions: covariate missingness, monotone missingness patterns, and multiple missing outcomes.
- Roadmap estimators: multiple imputation, doubly robust missing-data estimators, and sensitivity bounds for MNAR.
- Roadmap diagnostics: missingness by covariate quantile and overlap diagnostics for observation probabilities.

### 6. Clustered Or Multilevel Data

- Implemented now: fixed-size clustered continuous-outcome DGPs, ICC-driven random intercept variance, optional cluster-level confounder, and manual CR1 cluster-robust OLS SEs.
- Roadmap contract additions: variable cluster sizes, binary/count clustered outcomes, cluster-weighted estimands, and random slopes.
- Roadmap estimators: mixed models, GEE, cluster-level IPW, and small-sample corrections.
- Roadmap diagnostics: within-cluster treatment variation and cluster-weighted vs individual-weighted target comparisons.

### 7. DGP Calibration Engine

- Implemented now: deterministic bisection or closed-form calibration for treatment prevalence, binary baseline prevalence, count baseline rate, and ICC.
- Roadmap targets: binary risk difference, count rate ratio, overlap strength, and user-selected positivity thresholds.
- Roadmap reporting: calibration traces, richer failure diagnostics, and links from calibrated contracts to downstream reports.

### 8. Longitudinal Treatment Regimes

- Contract additions: time index, time-varying confounders, treatment history, regimes.
- Truth engine: g-formula or oracle simulation under each regime.
- Estimators: sequential g-computation, marginal structural models, longitudinal AIPW.
- Diagnostics: time-specific positivity, censoring/treatment weights, history support.
- Reporting: regime contrast plots and time-varying overlap warnings.

### 9. Survival Outcomes With Censoring

- Contract additions: event-time model, censoring model, administrative follow-up, target time horizon.
- Truth engine: survival curves, RMST, cumulative incidence, oracle regime curves.
- Estimators: Kaplan-Meier contrasts, Cox models, IPW censoring adjustment, RMST estimators.
- Diagnostics: censoring positivity, event counts, horizon-specific coverage.
- Reporting: survival/RMST plots and censoring diagnostics.

### 10. Panel Forecasting Simulation

- Contract additions: panel units, time series dynamics, interventions, train/test splits.
- Truth engine: known future targets or counterfactual forecast paths.
- Estimators: baseline forecasts, panel regressions, synthetic controls, ML forecasters.
- Diagnostics: forecast bias, RMSE/MAE, calibration, leakage checks.
- Reporting: forecast-path plots and metric tables.

### 11. Network And Interference Simulations

- Contract additions: network structure, exposure mappings, spillover effects, and partial interference groups.
- Truth engine: direct and spillover estimands under configured exposure regimes.
- Estimators: exposure-mapping contrasts and cluster-level summaries.
- Diagnostics: network degree distribution, exposure support, and interference strength checks.
- Reporting: network-aware assumptions and spillover-effect plots.

## Registration Philosophy

Future templates should be registered through a small template registry rather than a heavy plugin system. Each template should ship with:

- A schema contract.
- A truth engine.
- At least one simulator test with known expected truth.
- Estimator and diagnostics tests.
- A concise example YAML.
- A report section explaining how to interpret the target estimand.
