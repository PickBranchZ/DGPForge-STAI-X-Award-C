"""Simulation engine for the cross-sectional causal ATE template."""

from __future__ import annotations

import numpy as np
import pandas as pd

from dgpforge.schema import DGPContract


def logistic(x: np.ndarray) -> np.ndarray:
    """Numerically stable logistic transform."""
    clipped = np.clip(x, -35, 35)
    return 1.0 / (1.0 + np.exp(-clipped))


def _safe_exp(x: np.ndarray) -> np.ndarray:
    return np.exp(np.clip(x, -35, 35))


def _sample_count(
    rng: np.random.Generator,
    mu: np.ndarray,
    contract: DGPContract,
) -> np.ndarray:
    overdispersion = contract.outcome.overdispersion
    if overdispersion.enabled:
        theta = overdispersion.theta
        gamma_mean = np.clip(mu, 0.0, None)
        gamma_scale = np.where(gamma_mean > 0, gamma_mean / theta, 0.0)
        poisson_rate = rng.gamma(shape=theta, scale=gamma_scale)
        return rng.poisson(poisson_rate).astype(float)
    return rng.poisson(np.clip(mu, 0.0, None)).astype(float)


def cluster_outcome_sd(contract: DGPContract) -> float:
    clusters = contract.clusters
    if not clusters.enabled:
        return 0.0
    if clusters.icc is not None:
        noise_sd = 1.0 if contract.outcome.noise_sd is None else contract.outcome.noise_sd
        return float(np.sqrt(clusters.icc * noise_sd**2 / max(1.0 - clusters.icc, 1e-9)))
    return float(clusters.random_intercept.outcome_sd or 0.0)


def _cluster_ids(n: int, contract: DGPContract) -> np.ndarray:
    clusters = contract.clusters
    if not clusters.enabled:
        return np.zeros(n, dtype=int)
    expected_n = clusters.n_clusters * clusters.cluster_size
    if n == expected_n:
        return np.repeat(np.arange(clusters.n_clusters), clusters.cluster_size)
    repeats = int(np.ceil(n / clusters.n_clusters))
    return np.repeat(np.arange(clusters.n_clusters), repeats)[:n]


def _add_clusters(
    frame: pd.DataFrame,
    contract: DGPContract,
    rng: np.random.Generator,
    n: int,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    clusters = contract.clusters
    if not clusters.enabled:
        return None, None
    ids = _cluster_ids(n, contract)
    frame[clusters.cluster_id] = ids.astype(float)
    outcome_sd = cluster_outcome_sd(contract)
    treatment_sd = clusters.random_intercept.treatment_sd
    outcome_intercepts = rng.normal(0.0, outcome_sd, size=clusters.n_clusters)
    treatment_intercepts = rng.normal(0.0, treatment_sd, size=clusters.n_clusters)
    frame["_cluster_outcome_intercept"] = outcome_intercepts[ids]
    frame["_cluster_treatment_intercept"] = treatment_intercepts[ids]
    confounder = clusters.cluster_level_confounder
    if confounder.enabled:
        values = rng.normal(confounder.mean, confounder.sd, size=clusters.n_clusters)
        frame[confounder.name] = values[ids]
    return outcome_intercepts[ids], treatment_intercepts[ids]


def _add_unobserved_confounder(
    frame: pd.DataFrame,
    contract: DGPContract,
    rng: np.random.Generator,
    n: int,
) -> np.ndarray | None:
    unobserved = contract.unobserved_confounder
    if not unobserved.enabled:
        return None
    values = rng.normal(loc=unobserved.mean, scale=unobserved.sd, size=n)
    frame[unobserved.name] = values
    return values


def _calibrate_probability_intercept(linear_predictor: np.ndarray, target: float) -> float:
    if target <= 0:
        return -80.0
    if target >= 1:
        return 80.0
    low, high = -40.0, 40.0
    for _ in range(80):
        mid = (low + high) / 2.0
        mean_probability = float(logistic(linear_predictor + mid).mean())
        if mean_probability < target:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def _apply_missing_data(
    frame: pd.DataFrame,
    contract: DGPContract,
    rng: np.random.Generator,
) -> None:
    missing = contract.missing_data
    if not missing.enabled:
        return
    target = missing.target
    full_name = f"{target}_full"
    frame[full_name] = frame[target].to_numpy(copy=True)
    n = len(frame)
    if missing.mechanism == "MCAR":
        missing_probability = np.full(n, missing.rate, dtype=float)
    else:
        linear_predictor = np.full(n, missing.formula.get("intercept", 0.0), dtype=float)
        for term, coefficient in missing.formula.items():
            if term == "intercept":
                continue
            source = full_name if term == target else term
            linear_predictor += coefficient * frame[source].to_numpy(dtype=float)
        shift = _calibrate_probability_intercept(linear_predictor, missing.rate)
        missing_probability = logistic(linear_predictor + shift)
    observed = rng.binomial(1, 1.0 - missing_probability, size=n).astype(float)
    indicator_name = f"{missing.missing_indicator_prefix}_{target}"
    frame[indicator_name] = observed
    frame[f"missing_probability_{target}"] = missing_probability
    frame.loc[observed == 0, target] = np.nan


def simulate_dataset(contract: DGPContract, n: int, seed: int | None = None) -> pd.DataFrame:
    """Generate one synthetic dataset with known propensities and potential outcomes."""
    rng = np.random.default_rng(contract.seed if seed is None else seed)
    data: dict[str, np.ndarray] = {}

    for name, spec in contract.covariates.items():
        if spec.type == "continuous":
            assert spec.mean is not None
            assert spec.sd is not None
            data[name] = rng.normal(loc=spec.mean, scale=spec.sd, size=n)
        else:
            assert spec.p is not None
            data[name] = rng.binomial(1, spec.p, size=n).astype(float)

    frame = pd.DataFrame(data)
    cluster_outcome_values, cluster_treatment_values = _add_clusters(frame, contract, rng, n)
    unobserved_values = _add_unobserved_confounder(frame, contract, rng, n)

    treatment_formula = contract.treatment.formula
    intercept = treatment_formula.get("intercept", 0.0)
    linear_predictor = np.full(n, intercept, dtype=float)
    if contract.treatment.assignment == "logistic":
        for term, coefficient in treatment_formula.items():
            if term != "intercept":
                linear_predictor += coefficient * frame[term].to_numpy()
        if unobserved_values is not None:
            linear_predictor += (
                contract.unobserved_confounder.treatment_coefficient * unobserved_values
            )
        if cluster_treatment_values is not None:
            linear_predictor += cluster_treatment_values
        cluster_confounder = contract.clusters.cluster_level_confounder
        if contract.clusters.enabled and cluster_confounder.enabled:
            linear_predictor += (
                cluster_confounder.treatment_coefficient * frame[cluster_confounder.name].to_numpy()
            )
    propensity = logistic(linear_predictor)
    treatment = rng.binomial(1, propensity, size=n).astype(float)

    outcome_coefficients = contract.outcome.coefficients
    baseline = np.full(n, outcome_coefficients.get("intercept", 0.0), dtype=float)
    for term, coefficient in outcome_coefficients.items():
        if term != "intercept":
            baseline += coefficient * frame[term].to_numpy()
    if unobserved_values is not None:
        baseline += contract.unobserved_confounder.outcome_coefficient * unobserved_values
    if cluster_outcome_values is not None:
        baseline += cluster_outcome_values
    cluster_confounder = contract.clusters.cluster_level_confounder
    if contract.clusters.enabled and cluster_confounder.enabled:
        baseline += (
            cluster_confounder.outcome_coefficient * frame[cluster_confounder.name].to_numpy()
        )

    heterogeneity = contract.outcome.treatment_effect_heterogeneity
    logit_tau = np.full(n, contract.outcome.treatment_effect, dtype=float)
    if heterogeneity.enabled:
        assert heterogeneity.modifier is not None
        logit_tau += heterogeneity.coefficient * frame[heterogeneity.modifier].to_numpy()

    if contract.outcome.type == "binary":
        p0 = logistic(baseline)
        p1 = logistic(baseline + logit_tau)
        y0 = rng.binomial(1, p0, size=n).astype(float)
        y1 = rng.binomial(1, p1, size=n).astype(float)
        observed_y = treatment * y1 + (1.0 - treatment) * y0
        tau = p1 - p0
        frame["p0"] = p0
        frame["p1"] = p1
        frame["logit_tau"] = logit_tau
    elif contract.outcome.type == "count":
        exposure_spec = contract.outcome.exposure
        assert exposure_spec is not None
        exposure = rng.lognormal(
            mean=exposure_spec.meanlog,
            sigma=exposure_spec.sdlog,
            size=n,
        )
        rate0 = _safe_exp(baseline)
        rate1 = _safe_exp(baseline + logit_tau)
        mu0 = exposure * rate0
        mu1 = exposure * rate1
        y0 = _sample_count(rng, mu0, contract)
        y1 = _sample_count(rng, mu1, contract)
        observed_y = treatment * y1 + (1.0 - treatment) * y0
        tau = rate1 - rate0
        frame[exposure_spec.name] = exposure
        frame["rate0"] = rate0
        frame["rate1"] = rate1
        frame["mu0"] = mu0
        frame["mu1"] = mu1
        frame["log_rate_tau"] = logit_tau
    else:
        tau = logit_tau
        y0 = baseline
        y1 = baseline + tau
        noise_sd = 1.0 if contract.outcome.noise_sd is None else contract.outcome.noise_sd
        noise = rng.normal(loc=0.0, scale=noise_sd, size=n)
        observed_y = y0 + treatment * tau + noise

    frame["propensity"] = propensity
    frame[contract.treatment.name] = treatment
    frame["Y0"] = y0
    frame["Y1"] = y1
    frame["tau"] = tau
    frame[contract.outcome.name] = observed_y
    _apply_missing_data(frame, contract, rng)
    return frame
