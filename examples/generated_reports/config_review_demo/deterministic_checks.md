# Deterministic Checks

- **config_path**: `examples\causal_binary_outcome.yaml`
- **validation_status**: `pass`
- **validation_errors**: `[]`
- **schema_version**: `1.0`
- **name**: `binary_outcome_marginal_risk_demo`
- **template**: `cross_sectional_binary_treatment_binary_outcome`
- **outcome_type**: `binary`
- **estimand**: `{
  "contrast": "E[Y(1) - Y(0)]",
  "name": "marginal_risk_difference",
  "primary": "risk_difference"
}`
- **truth_engine**: `oracle Monte Carlo over counterfactual probabilities`
- **estimators**: `[
  "naive_risk_difference",
  "logistic_gcomp_risk_difference",
  "ipw_risk_difference",
  "aipw_risk_difference"
]`
- **estimator_compatibility**: `schema accepted estimator names for this contract`
- **se_ci_status**: `binary risk estimators expose lightweight implemented intervals where available`
- **sample_sizes**: `[
  800,
  1600
]`
- **n_replications**: `120`
- **low_replication_warning**: `False`
- **weak_overlap_risk**: `False`
- **missingness_assumptions**: `{
  "apply_to": [
    "Y"
  ],
  "enabled": false,
  "formula": {},
  "mechanism": "MCAR",
  "missing_indicator_prefix": "R",
  "rate": 0.0,
  "target": "Y"
}`
- **unobserved_confounding**: `{
  "distribution": "normal",
  "enabled": false,
  "mean": 0.0,
  "name": "U",
  "observed": false,
  "outcome_coefficient": 0.0,
  "sd": 1.0,
  "treatment_coefficient": 0.0
}`
- **clustering**: `{
  "cluster_id": "cluster_id",
  "cluster_level_confounder": {
    "distribution": "normal",
    "enabled": false,
    "mean": 0.0,
    "name": "Z_cluster",
    "outcome_coefficient": 0.0,
    "sd": 1.0,
    "treatment_coefficient": 0.0
  },
  "cluster_size": 1,
  "cluster_size_distribution": "fixed",
  "enabled": false,
  "icc": null,
  "n_clusters": 1,
  "random_intercept": {
    "outcome_sd": null,
    "treatment_sd": 0.0
  }
}`
- **calibration_target_caveat**: `calibration configs are reviewed through dgpforge calibrate, not this DGP contract review`
