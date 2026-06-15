"""Estimators for the marginal ATE benchmark."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from typing import Callable

import numpy as np
import pandas as pd

from dgpforge.schema import DGPContract
from dgpforge.simulate import logistic


Z_VALUE = 1.959963984540054


@dataclass(frozen=True)
class EstimatorResult:
    estimator: str
    estimate: float
    se: float
    ci_lower: float
    ci_upper: float
    status: str = "ok"
    error_type: str | None = None
    error_message: str | None = None

    def as_dict(self) -> dict[str, float | str | None]:
        return asdict(self)


def _ci(estimate: float, se: float) -> tuple[float, float]:
    if not np.isfinite(se):
        return float("nan"), float("nan")
    return float(estimate - Z_VALUE * se), float(estimate + Z_VALUE * se)


def _nan_result(
    estimator: str,
    *,
    status: str = "not_applicable",
    error_type: str | None = None,
    error_message: str | None = None,
) -> EstimatorResult:
    return EstimatorResult(
        estimator,
        float("nan"),
        float("nan"),
        float("nan"),
        float("nan"),
        status=status,
        error_type=error_type,
        error_message=error_message,
    )


def _rename_result(result: EstimatorResult, estimator_name: str) -> EstimatorResult:
    return EstimatorResult(
        estimator_name,
        result.estimate,
        result.se,
        result.ci_lower,
        result.ci_upper,
        status=result.status,
        error_type=result.error_type,
        error_message=result.error_message,
    )


def _covariate_names(
    contract: DGPContract,
    omit: tuple[str, ...] | None = None,
    include_unobserved: bool = False,
) -> list[str]:
    omit_set = set(omit or ())
    names = [name for name in contract.covariates if name not in omit_set]
    unobserved = contract.unobserved_confounder
    if (
        unobserved.enabled
        and unobserved.name not in omit_set
        and (unobserved.observed or include_unobserved)
    ):
        names.append(unobserved.name)
    cluster_confounder = contract.clusters.cluster_level_confounder
    if (
        contract.clusters.enabled
        and cluster_confounder.enabled
        and cluster_confounder.name not in omit_set
    ):
        names.append(cluster_confounder.name)
    return names


def _default_omit_confounder(contract: DGPContract) -> tuple[str, ...]:
    confounders = [name for name, spec in contract.covariates.items() if spec.role == "confounder"]
    if confounders:
        return tuple(confounders)
    treatment_terms = [name for name in contract.treatment.formula if name != "intercept"]
    if treatment_terms:
        return tuple(treatment_terms)
    names = list(contract.covariates)
    return (names[-1],) if names else ()


def _default_omit_outcome_features(contract: DGPContract) -> tuple[str, ...]:
    feature_names = [
        name
        for name, spec in contract.covariates.items()
        if spec.role in {"confounder", "prognostic"}
    ]
    if feature_names:
        return tuple(feature_names)
    return _default_omit_confounder(contract)


def _covariate_matrix(
    data: pd.DataFrame,
    contract: DGPContract,
    omit: tuple[str, ...] | None = None,
    include_unobserved: bool = False,
) -> np.ndarray:
    columns = _covariate_names(
        contract,
        omit=omit,
        include_unobserved=include_unobserved,
    )
    if not columns:
        return np.empty((len(data), 0))
    return data[columns].to_numpy(dtype=float)


def _ols(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    xtx_inv = np.linalg.pinv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    residuals = y - x @ beta
    degrees = max(len(y) - x.shape[1], 1)
    sigma2 = float((residuals @ residuals) / degrees)
    covariance = sigma2 * xtx_inv
    return beta, covariance


def _weighted_ols_beta(y: np.ndarray, x: np.ndarray, weights: np.ndarray) -> np.ndarray:
    clipped_weights = np.clip(weights, 1e-9, None)
    xtw = x.T * clipped_weights
    return np.linalg.pinv(xtw @ x) @ (xtw @ y)


def _cluster_robust_covariance(
    y: np.ndarray,
    x: np.ndarray,
    cluster_ids: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    beta, _ = _ols(y, x)
    residuals = y - x @ beta
    bread = np.linalg.pinv(x.T @ x)
    meat = np.zeros((x.shape[1], x.shape[1]))
    unique_clusters = np.unique(cluster_ids)
    for cluster in unique_clusters:
        mask = cluster_ids == cluster
        score = x[mask].T @ residuals[mask]
        meat += np.outer(score, score)
    n = len(y)
    p = x.shape[1]
    g = len(unique_clusters)
    correction = 1.0
    if g > 1 and n > p:
        correction = (g / (g - 1.0)) * ((n - 1.0) / (n - p))
    covariance = correction * bread @ meat @ bread
    return beta, covariance


def _complete_case_data(data: pd.DataFrame, contract: DGPContract) -> pd.DataFrame:
    required = [contract.outcome.name, contract.treatment.name, *_covariate_names(contract)]
    if contract.outcome.type == "count":
        exposure_spec = contract.outcome.exposure
        assert exposure_spec is not None
        required.append(exposure_spec.name)
    return data.dropna(subset=required).copy()


def _linear_predictions(y: np.ndarray, covariates: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if int(mask.sum()) <= covariates.shape[1] + 1:
        return np.full(len(y), float(np.mean(y[mask])) if mask.any() else float(np.mean(y)))
    design = np.column_stack([np.ones(mask.sum()), covariates[mask]])
    beta, _ = _ols(y[mask], design)
    all_design = np.column_stack([np.ones(len(y)), covariates])
    return all_design @ beta


def _pooled_no_interaction_predictions(
    y: np.ndarray, treatment: np.ndarray, covariates: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    design = np.column_stack([np.ones(len(y)), treatment, covariates])
    beta, _ = _ols(y, design)
    treated_design = np.column_stack([np.ones(len(y)), np.ones(len(y)), covariates])
    control_design = np.column_stack([np.ones(len(y)), np.zeros(len(y)), covariates])
    return treated_design @ beta, control_design @ beta


def _fit_propensity(
    treatment: np.ndarray,
    covariates: np.ndarray,
    clip: float = 0.01,
    max_iter: int = 80,
    l2: float = 1e-4,
) -> np.ndarray:
    if covariates.shape[1] == 0:
        prevalence = np.clip(float(treatment.mean()), clip, 1 - clip)
        return np.full(len(treatment), prevalence)

    x = np.column_stack([np.ones(len(treatment)), covariates])
    beta = np.zeros(x.shape[1], dtype=float)
    penalty = np.eye(x.shape[1]) * l2
    penalty[0, 0] = 0.0

    for _ in range(max_iter):
        propensities = logistic(x @ beta)
        weights = np.clip(propensities * (1.0 - propensities), 1e-6, None)
        hessian = x.T @ (x * weights[:, None]) + penalty
        gradient = x.T @ (treatment - propensities) - penalty @ beta
        delta = np.linalg.pinv(hessian) @ gradient
        delta = np.clip(delta, -2.5, 2.5)
        beta += delta
        if np.linalg.norm(delta) < 1e-7:
            break

    return np.clip(logistic(x @ beta), clip, 1 - clip)


def _fit_logistic_beta(
    y: np.ndarray,
    x: np.ndarray,
    max_iter: int = 80,
    l2: float = 1e-4,
) -> np.ndarray | None:
    if len(np.unique(y)) < 2:
        return None
    beta = np.zeros(x.shape[1], dtype=float)
    penalty = np.eye(x.shape[1]) * l2
    penalty[0, 0] = 0.0
    for _ in range(max_iter):
        probabilities = logistic(x @ beta)
        weights = np.clip(probabilities * (1.0 - probabilities), 1e-6, None)
        hessian = x.T @ (x * weights[:, None]) + penalty
        gradient = x.T @ (y - probabilities) - penalty @ beta
        delta = np.linalg.pinv(hessian) @ gradient
        delta = np.clip(delta, -2.5, 2.5)
        beta += delta
        if np.linalg.norm(delta) < 1e-7:
            break
    if not np.isfinite(beta).all():
        return None
    return beta


def _logistic_predictions(
    y: np.ndarray,
    covariates: np.ndarray,
    mask: np.ndarray,
) -> np.ndarray:
    if int(mask.sum()) <= covariates.shape[1] + 1 or len(np.unique(y[mask])) < 2:
        fallback = float(np.mean(y[mask])) if mask.any() else float(np.mean(y))
        return np.full(len(y), np.clip(fallback, 0.01, 0.99))
    design = np.column_stack([np.ones(mask.sum()), covariates[mask]])
    beta = _fit_logistic_beta(y[mask], design)
    if beta is None:
        fallback = float(np.mean(y[mask]))
        return np.full(len(y), np.clip(fallback, 0.01, 0.99))
    all_design = np.column_stack([np.ones(len(y)), covariates])
    return np.clip(logistic(all_design @ beta), 0.01, 0.99)


def _logistic_gcomp(
    data: pd.DataFrame,
    contract: DGPContract,
    estimator_name: str,
    include_unobserved: bool = False,
) -> EstimatorResult:
    treatment = data[contract.treatment.name].to_numpy(dtype=float)
    outcome = data[contract.outcome.name].to_numpy(dtype=float)
    if len(np.unique(treatment)) < 2:
        return _nan_result(estimator_name)
    covariates = _covariate_matrix(
        data,
        contract,
        include_unobserved=include_unobserved,
    )
    design = np.column_stack([np.ones(len(data)), treatment, covariates])
    beta = _fit_logistic_beta(outcome, design)
    if beta is None:
        return _nan_result(estimator_name)
    treated_design = np.column_stack([np.ones(len(data)), np.ones(len(data)), covariates])
    control_design = np.column_stack([np.ones(len(data)), np.zeros(len(data)), covariates])
    p1 = np.clip(logistic(treated_design @ beta), 0.01, 0.99)
    p0 = np.clip(logistic(control_design @ beta), 0.01, 0.99)
    score = p1 - p0
    estimate = float(score.mean())
    se = float(score.std(ddof=1) / np.sqrt(len(score))) if len(score) > 1 else 0.0
    lower, upper = _ci(estimate, se)
    return EstimatorResult(estimator_name, estimate, se, lower, upper)


def _fit_poisson_offset_beta(
    y: np.ndarray,
    x: np.ndarray,
    offset: np.ndarray,
    max_iter: int = 80,
    l2: float = 1e-6,
) -> np.ndarray | None:
    beta = np.zeros(x.shape[1], dtype=float)
    penalty = np.eye(x.shape[1]) * l2
    penalty[0, 0] = 0.0
    for _ in range(max_iter):
        eta_without_offset = x @ beta
        eta = np.clip(offset + eta_without_offset, -35, 35)
        mu = np.clip(np.exp(eta), 1e-9, None)
        z = eta_without_offset + (y - mu) / mu
        hessian = x.T @ (x * mu[:, None]) + penalty
        gradient_target = x.T @ (mu * z)
        beta_next = np.linalg.pinv(hessian) @ gradient_target
        delta = np.clip(beta_next - beta, -2.5, 2.5)
        beta += delta
        if np.linalg.norm(delta) < 1e-7:
            break
    if not np.isfinite(beta).all():
        return None
    return beta


def _count_exposure(data: pd.DataFrame, contract: DGPContract) -> np.ndarray:
    exposure_spec = contract.outcome.exposure
    assert exposure_spec is not None
    exposure_name = exposure_spec.name
    return np.clip(data[exposure_name].to_numpy(dtype=float), 1e-12, None)


def _rate_difference_result(
    estimator_name: str,
    rate1: float,
    rate0: float,
    se: float | None = None,
) -> EstimatorResult:
    estimate = float(rate1 - rate0)
    if se is None:
        return EstimatorResult(estimator_name, estimate, float("nan"), float("nan"), float("nan"))
    lower, upper = _ci(estimate, se)
    return EstimatorResult(estimator_name, estimate, float(se), lower, upper)


def naive_difference(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    treatment = data[contract.treatment.name].to_numpy(dtype=float)
    outcome = data[contract.outcome.name].to_numpy(dtype=float)
    treated = outcome[treatment == 1]
    control = outcome[treatment == 0]
    if len(treated) == 0 or len(control) == 0:
        return _nan_result("naive_difference")
    estimate = float(treated.mean() - control.mean())
    se = float(np.sqrt(treated.var(ddof=1) / len(treated) + control.var(ddof=1) / len(control)))
    lower, upper = _ci(estimate, se)
    return EstimatorResult("naive_difference", estimate, se, lower, upper)


def naive_risk_difference(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    treatment = data[contract.treatment.name].to_numpy(dtype=float)
    outcome = data[contract.outcome.name].to_numpy(dtype=float)
    treated = outcome[treatment == 1]
    control = outcome[treatment == 0]
    if len(treated) == 0 or len(control) == 0:
        return _nan_result("naive_risk_difference")
    estimate = float(treated.mean() - control.mean())
    se = float(np.sqrt(treated.var(ddof=1) / len(treated) + control.var(ddof=1) / len(control)))
    lower, upper = _ci(estimate, se)
    return EstimatorResult("naive_risk_difference", estimate, se, lower, upper)


def logistic_gcomp_risk_difference(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    return _logistic_gcomp(data, contract, "logistic_gcomp_risk_difference")


def naive_rate_difference(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    treatment = data[contract.treatment.name].to_numpy(dtype=float)
    outcome = data[contract.outcome.name].to_numpy(dtype=float)
    exposure = _count_exposure(data, contract)
    treated = treatment == 1
    control = treatment == 0
    if treated.sum() == 0 or control.sum() == 0:
        return _nan_result("naive_rate_difference")
    exposure1 = float(exposure[treated].sum())
    exposure0 = float(exposure[control].sum())
    if exposure1 <= 0 or exposure0 <= 0:
        return _nan_result("naive_rate_difference")
    events1 = float(outcome[treated].sum())
    events0 = float(outcome[control].sum())
    rate1 = float(events1 / exposure1)
    rate0 = float(events0 / exposure0)
    se = None
    if not contract.outcome.overdispersion.enabled:
        variance = max(events1 / exposure1**2 + events0 / exposure0**2, 0.0)
        se = float(np.sqrt(variance))
    return _rate_difference_result("naive_rate_difference", rate1, rate0, se)


def naive_difference_complete_case(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    complete = _complete_case_data(data, contract)
    if complete.empty:
        return _nan_result("naive_difference_complete_case")
    result = naive_difference(complete, contract)
    return _rename_result(result, "naive_difference_complete_case")


def poisson_offset_gcomp_rate_difference(
    data: pd.DataFrame, contract: DGPContract
) -> EstimatorResult:
    treatment = data[contract.treatment.name].to_numpy(dtype=float)
    outcome = data[contract.outcome.name].to_numpy(dtype=float)
    exposure = _count_exposure(data, contract)
    if len(np.unique(treatment)) < 2:
        return _nan_result("poisson_offset_gcomp_rate_difference")
    covariates = _covariate_matrix(data, contract)
    design = np.column_stack([np.ones(len(data)), treatment, covariates])
    beta = _fit_poisson_offset_beta(outcome, design, np.log(exposure))
    if beta is None:
        return _nan_result("poisson_offset_gcomp_rate_difference")
    treated_design = np.column_stack([np.ones(len(data)), np.ones(len(data)), covariates])
    control_design = np.column_stack([np.ones(len(data)), np.zeros(len(data)), covariates])
    mu1 = np.exp(np.clip(np.log(exposure) + treated_design @ beta, -35, 35))
    mu0 = np.exp(np.clip(np.log(exposure) + control_design @ beta, -35, 35))
    exposure_total = float(exposure.sum())
    if exposure_total <= 0:
        return _nan_result("poisson_offset_gcomp_rate_difference")
    rate1 = float(mu1.sum() / exposure_total)
    rate0 = float(mu0.sum() / exposure_total)
    return _rate_difference_result("poisson_offset_gcomp_rate_difference", rate1, rate0)


def adjusted_ols(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    return _adjusted_ols(data, contract, "adjusted_ols")


def adjusted_ols_naive_se(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    return _adjusted_ols(data, contract, "adjusted_ols_naive_se")


def adjusted_ols_cluster_robust(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    if not contract.clusters.enabled or contract.outcome.type != "continuous":
        return _nan_result("adjusted_ols_cluster_robust")
    treatment = data[contract.treatment.name].to_numpy(dtype=float)
    outcome = data[contract.outcome.name].to_numpy(dtype=float)
    if len(np.unique(treatment)) < 2:
        return _nan_result("adjusted_ols_cluster_robust")
    covariates = _covariate_matrix(data, contract)
    design = np.column_stack([np.ones(len(data)), treatment, covariates])
    cluster_ids = data[contract.clusters.cluster_id].to_numpy()
    beta, covariance = _cluster_robust_covariance(outcome, design, cluster_ids)
    estimate = float(beta[1])
    se = float(np.sqrt(max(covariance[1, 1], 0.0)))
    lower, upper = _ci(estimate, se)
    return EstimatorResult("adjusted_ols_cluster_robust", estimate, se, lower, upper)


def adjusted_ols_complete_case(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    complete = _complete_case_data(data, contract)
    if complete.empty:
        return _nan_result("adjusted_ols_complete_case")
    return _adjusted_ols(complete, contract, "adjusted_ols_complete_case")


def adjusted_ols_missingness_ipw(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    if not contract.missing_data.enabled or contract.outcome.type != "continuous":
        return _nan_result("adjusted_ols_missingness_ipw")
    indicator_name = f"{contract.missing_data.missing_indicator_prefix}_{contract.outcome.name}"
    if indicator_name not in data:
        return _nan_result("adjusted_ols_missingness_ipw")
    observed = data[indicator_name].to_numpy(dtype=float)
    complete = _complete_case_data(data, contract)
    if complete.empty or len(np.unique(complete[contract.treatment.name])) < 2:
        return _nan_result("adjusted_ols_missingness_ipw")

    missingness_covariates = np.column_stack(
        [
            data[contract.treatment.name].to_numpy(dtype=float),
            _covariate_matrix(data, contract),
        ]
    )
    observation_probability = _fit_propensity(observed, missingness_covariates)
    complete_probability = observation_probability[complete.index.to_numpy()]
    treatment = complete[contract.treatment.name].to_numpy(dtype=float)
    outcome = complete[contract.outcome.name].to_numpy(dtype=float)
    covariates = _covariate_matrix(complete, contract)
    design = np.column_stack([np.ones(len(complete)), treatment, covariates])
    weights = 1.0 / np.clip(complete_probability, 0.01, 1.0)
    beta = _weighted_ols_beta(outcome, design, weights)
    estimate = float(beta[1])
    return EstimatorResult(
        "adjusted_ols_missingness_ipw",
        estimate,
        float("nan"),
        float("nan"),
        float("nan"),
    )


def _adjusted_ols(
    data: pd.DataFrame,
    contract: DGPContract,
    estimator_name: str,
    omit: tuple[str, ...] | None = None,
    include_unobserved: bool = False,
) -> EstimatorResult:
    treatment = data[contract.treatment.name].to_numpy(dtype=float)
    outcome = data[contract.outcome.name].to_numpy(dtype=float)
    if len(np.unique(treatment)) < 2:
        return _nan_result(estimator_name)
    covariates = _covariate_matrix(
        data,
        contract,
        omit=omit,
        include_unobserved=include_unobserved,
    )
    design = np.column_stack([np.ones(len(data)), treatment, covariates])
    beta, covariance = _ols(outcome, design)
    estimate = float(beta[1])
    se = float(np.sqrt(max(covariance[1, 1], 0.0)))
    lower, upper = _ci(estimate, se)
    return EstimatorResult(estimator_name, estimate, se, lower, upper)


def adjusted_ols_omit_confounder(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    return _adjusted_ols(
        data,
        contract,
        "adjusted_ols_omit_confounder",
        omit=_default_omit_confounder(contract),
    )


def ipw(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    return _ipw(data, contract, "ipw")


def _ipw(
    data: pd.DataFrame,
    contract: DGPContract,
    estimator_name: str,
    omit: tuple[str, ...] | None = None,
) -> EstimatorResult:
    treatment = data[contract.treatment.name].to_numpy(dtype=float)
    outcome = data[contract.outcome.name].to_numpy(dtype=float)
    if len(np.unique(treatment)) < 2:
        return _nan_result(estimator_name)
    covariates = _covariate_matrix(data, contract, omit=omit)
    propensity = _fit_propensity(treatment, covariates)
    score = treatment * outcome / propensity - (1.0 - treatment) * outcome / (1.0 - propensity)
    estimate = float(score.mean())
    se = float(score.std(ddof=1) / np.sqrt(len(score)))
    lower, upper = _ci(estimate, se)
    return EstimatorResult(estimator_name, estimate, se, lower, upper)


def ipw_omit_confounder(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    return _ipw(data, contract, "ipw_omit_confounder", omit=_default_omit_confounder(contract))


def aipw(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    return _aipw(data, contract, "aipw")


def aipw_complete_case(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    complete = _complete_case_data(data, contract)
    if complete.empty:
        return _nan_result("aipw_complete_case")
    return _aipw(complete, contract, "aipw_complete_case")


def _aipw(
    data: pd.DataFrame,
    contract: DGPContract,
    estimator_name: str,
    ps_omit: tuple[str, ...] | None = None,
    outcome_omit: tuple[str, ...] | None = None,
    pooled_outcome: bool = False,
) -> EstimatorResult:
    treatment = data[contract.treatment.name].to_numpy(dtype=float)
    outcome = data[contract.outcome.name].to_numpy(dtype=float)
    if len(np.unique(treatment)) < 2:
        return _nan_result(estimator_name)
    ps_covariates = _covariate_matrix(data, contract, omit=ps_omit)
    outcome_covariates = _covariate_matrix(data, contract, omit=outcome_omit)
    propensity = _fit_propensity(treatment, ps_covariates)
    if pooled_outcome:
        m1, m0 = _pooled_no_interaction_predictions(outcome, treatment, outcome_covariates)
    else:
        m1 = _linear_predictions(outcome, outcome_covariates, treatment == 1)
        m0 = _linear_predictions(outcome, outcome_covariates, treatment == 0)
    score = (
        m1
        - m0
        + treatment * (outcome - m1) / propensity
        - (1.0 - treatment) * (outcome - m0) / (1.0 - propensity)
    )
    estimate = float(score.mean())
    se = float(score.std(ddof=1) / np.sqrt(len(score)))
    lower, upper = _ci(estimate, se)
    return EstimatorResult(estimator_name, estimate, se, lower, upper)


def aipw_ps_misspecified(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    return _aipw(
        data,
        contract,
        "aipw_ps_misspecified",
        ps_omit=_default_omit_confounder(contract),
    )


def aipw_outcome_misspecified(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    return _aipw(
        data,
        contract,
        "aipw_outcome_misspecified",
        outcome_omit=_default_omit_outcome_features(contract),
        pooled_outcome=True,
    )


def aipw_double_misspecified(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    ps_omit = _default_omit_confounder(contract)
    outcome_omit = _default_omit_outcome_features(contract)
    return _aipw(
        data,
        contract,
        "aipw_double_misspecified",
        ps_omit=ps_omit,
        outcome_omit=outcome_omit,
        pooled_outcome=True,
    )


def ipw_risk_difference(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    return _ipw(data, contract, "ipw_risk_difference")


def ipw_rate_difference(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    treatment = data[contract.treatment.name].to_numpy(dtype=float)
    outcome = data[contract.outcome.name].to_numpy(dtype=float)
    exposure = _count_exposure(data, contract)
    if len(np.unique(treatment)) < 2:
        return _nan_result("ipw_rate_difference")
    covariates = _covariate_matrix(data, contract)
    propensity = _fit_propensity(treatment, covariates)
    treated_weight = treatment / propensity
    control_weight = (1.0 - treatment) / (1.0 - propensity)
    denominator1 = float((treated_weight * exposure).sum())
    denominator0 = float((control_weight * exposure).sum())
    if denominator1 <= 0 or denominator0 <= 0:
        return _nan_result("ipw_rate_difference")
    rate1 = float((treated_weight * outcome).sum() / denominator1)
    rate0 = float((control_weight * outcome).sum() / denominator0)
    return _rate_difference_result("ipw_rate_difference", rate1, rate0)


def logistic_gcomp_complete_case(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    complete = _complete_case_data(data, contract)
    if complete.empty:
        return _nan_result("logistic_gcomp_complete_case")
    return _logistic_gcomp(complete, contract, "logistic_gcomp_complete_case")


def rate_gcomp_complete_case(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    complete = _complete_case_data(data, contract)
    if complete.empty:
        return _nan_result("rate_gcomp_complete_case")
    result = poisson_offset_gcomp_rate_difference(complete, contract)
    return _rename_result(result, "rate_gcomp_complete_case")


def aipw_risk_difference(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    treatment = data[contract.treatment.name].to_numpy(dtype=float)
    outcome = data[contract.outcome.name].to_numpy(dtype=float)
    if len(np.unique(treatment)) < 2:
        return _nan_result("aipw_risk_difference")
    covariates = _covariate_matrix(data, contract)
    propensity = _fit_propensity(treatment, covariates)
    m1 = _logistic_predictions(outcome, covariates, treatment == 1)
    m0 = _logistic_predictions(outcome, covariates, treatment == 0)
    score = (
        m1
        - m0
        + treatment * (outcome - m1) / propensity
        - (1.0 - treatment) * (outcome - m0) / (1.0 - propensity)
    )
    estimate = float(score.mean())
    se = float(score.std(ddof=1) / np.sqrt(len(score)))
    lower, upper = _ci(estimate, se)
    return EstimatorResult("aipw_risk_difference", estimate, se, lower, upper)


def adjusted_oracle_includes_U(data: pd.DataFrame, contract: DGPContract) -> EstimatorResult:
    if not contract.unobserved_confounder.enabled:
        return _nan_result("adjusted_oracle_includes_U")
    if contract.outcome.type == "binary":
        return _logistic_gcomp(
            data,
            contract,
            "adjusted_oracle_includes_U",
            include_unobserved=True,
        )
    return _adjusted_ols(
        data,
        contract,
        "adjusted_oracle_includes_U",
        omit=None,
        include_unobserved=True,
    )


ESTIMATORS: dict[str, Callable[[pd.DataFrame, DGPContract], EstimatorResult]] = {
    "naive_difference": naive_difference,
    "adjusted_ols": adjusted_ols,
    "adjusted_ols_omit_confounder": adjusted_ols_omit_confounder,
    "adjusted_ols_naive_se": adjusted_ols_naive_se,
    "adjusted_ols_cluster_robust": adjusted_ols_cluster_robust,
    "ipw": ipw,
    "ipw_omit_confounder": ipw_omit_confounder,
    "aipw": aipw,
    "aipw_ps_misspecified": aipw_ps_misspecified,
    "aipw_outcome_misspecified": aipw_outcome_misspecified,
    "aipw_double_misspecified": aipw_double_misspecified,
    "naive_risk_difference": naive_risk_difference,
    "logistic_gcomp_risk_difference": logistic_gcomp_risk_difference,
    "ipw_risk_difference": ipw_risk_difference,
    "aipw_risk_difference": aipw_risk_difference,
    "adjusted_oracle_includes_U": adjusted_oracle_includes_U,
    "naive_rate_difference": naive_rate_difference,
    "poisson_offset_gcomp_rate_difference": poisson_offset_gcomp_rate_difference,
    "ipw_rate_difference": ipw_rate_difference,
    "naive_difference_complete_case": naive_difference_complete_case,
    "adjusted_ols_complete_case": adjusted_ols_complete_case,
    "aipw_complete_case": aipw_complete_case,
    "adjusted_ols_missingness_ipw": adjusted_ols_missingness_ipw,
    "logistic_gcomp_complete_case": logistic_gcomp_complete_case,
    "rate_gcomp_complete_case": rate_gcomp_complete_case,
}


def run_estimators(data: pd.DataFrame, contract: DGPContract) -> pd.DataFrame:
    """Run all estimators requested by the contract."""
    rows = []
    for estimator_name in contract.estimators:
        try:
            result = ESTIMATORS[estimator_name](data, contract)
        except Exception as exc:
            if os.environ.get("DGPFORGE_RAISE_ESTIMATOR_ERRORS") == "1":
                raise
            result = _nan_result(
                estimator_name,
                status="failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        rows.append(result.as_dict())
    return pd.DataFrame(rows)
