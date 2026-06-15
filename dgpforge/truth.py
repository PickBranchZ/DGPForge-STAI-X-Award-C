"""Known-truth estimand calculations."""

from __future__ import annotations

from dgpforge.schema import CovariateSpec, DGPContract
from dgpforge.simulate import simulate_dataset


EPSILON = 1e-9


def _covariate_expectation(spec: CovariateSpec) -> float:
    if spec.type == "continuous":
        assert spec.mean is not None
        return float(spec.mean)
    assert spec.p is not None
    return float(spec.p)


def analytical_ate(contract: DGPContract) -> float:
    """Return analytical ATE for the supported linear treatment-effect model."""
    if contract.outcome.type != "continuous":
        raise ValueError("analytical_ate is only defined for continuous linear outcomes")
    heterogeneity = contract.outcome.treatment_effect_heterogeneity
    ate = float(contract.outcome.treatment_effect)
    if heterogeneity.enabled and heterogeneity.coefficient != 0:
        assert heterogeneity.modifier is not None
        modifier = contract.covariates[heterogeneity.modifier]
        ate += float(heterogeneity.coefficient) * _covariate_expectation(modifier)
    return ate


def oracle_monte_carlo_ate(
    contract: DGPContract, n: int = 100_000, seed: int | None = None
) -> float:
    """Approximate true ATE by simulating a large oracle population."""
    oracle_seed = contract.seed + 99_001 if seed is None else seed
    data = simulate_dataset(contract, n=n, seed=oracle_seed)
    return float((data["Y1"] - data["Y0"]).mean())


def _odds(risk: float) -> float:
    clipped = min(max(risk, EPSILON), 1.0 - EPSILON)
    return clipped / (1.0 - clipped)


def binary_oracle_truth(
    contract: DGPContract, n: int = 100_000, seed: int | None = None
) -> dict[str, float | str]:
    """Approximate marginal binary-outcome estimands from oracle probabilities."""
    oracle_seed = contract.seed + 99_001 if seed is None else seed
    data = simulate_dataset(contract, n=n, seed=oracle_seed)
    ey1 = float(data["p1"].mean())
    ey0 = float(data["p0"].mean())
    risk_difference = ey1 - ey0
    risk_ratio = ey1 / ey0 if ey0 > EPSILON else float("nan")
    odds_ratio = _odds(ey1) / _odds(ey0)
    return {
        "truth": float(
            {
                "risk_difference": risk_difference,
                "risk_ratio": risk_ratio,
                "odds_ratio": odds_ratio,
            }[contract.estimand.primary]
        ),
        "primary_estimand": contract.estimand.primary,
        "true_EY1": ey1,
        "true_EY0": ey0,
        "true_risk_difference": risk_difference,
        "true_risk_ratio": float(risk_ratio),
        "true_odds_ratio": float(odds_ratio),
        "conditional_logistic_treatment_effect": float(contract.outcome.treatment_effect),
    }


def count_oracle_truth(
    contract: DGPContract, n: int = 100_000, seed: int | None = None
) -> dict[str, float | str]:
    """Approximate marginal count/rate estimands from oracle expected counts."""
    oracle_seed = contract.seed + 99_001 if seed is None else seed
    data = simulate_dataset(contract, n=n, seed=oracle_seed)
    exposure_spec = contract.outcome.exposure
    assert exposure_spec is not None
    exposure_name = exposure_spec.name
    exposure = data[exposure_name]
    exposure_total = float(exposure.sum())
    mu1_total = float(data["mu1"].sum())
    mu0_total = float(data["mu0"].sum())
    rate1 = mu1_total / exposure_total if exposure_total > EPSILON else float("nan")
    rate0 = mu0_total / exposure_total if exposure_total > EPSILON else float("nan")
    rate_difference = rate1 - rate0
    rate_ratio = rate1 / rate0 if rate0 > EPSILON else float("nan")
    log_rate_ratio = float("nan")
    if rate_ratio > EPSILON:
        import math

        log_rate_ratio = math.log(rate_ratio)
    primary = contract.estimand.primary
    return {
        "truth": float(
            {
                "rate_difference": rate_difference,
                "rate_ratio": rate_ratio,
                "log_rate_ratio": log_rate_ratio,
            }[primary]
        ),
        "primary_estimand": primary,
        "true_rate_1": float(rate1),
        "true_rate_0": float(rate0),
        "true_rate_difference": float(rate_difference),
        "true_rate_ratio": float(rate_ratio),
        "true_log_rate_ratio": float(log_rate_ratio),
        "true_mean_count_1": float(data["mu1"].mean()),
        "true_mean_count_0": float(data["mu0"].mean()),
        "exposure_scale": float(exposure_spec.scale),
        "conditional_log_rate_treatment_effect": float(contract.outcome.treatment_effect),
    }


def truth_details(contract: DGPContract, oracle_n: int = 100_000) -> dict[str, float | str]:
    """Return the scalar target plus auxiliary known-truth quantities."""
    if contract.outcome.type == "binary":
        return binary_oracle_truth(contract, n=oracle_n)
    if contract.outcome.type == "count":
        return count_oracle_truth(contract, n=oracle_n)
    truth = analytical_ate(contract)
    return {
        "truth": truth,
        "primary_estimand": "mean_difference",
        "true_mean_difference": truth,
        "true_ATE": truth,
    }


def true_ate(contract: DGPContract, oracle_n: int = 100_000) -> float:
    """Choose analytical or oracle truth according to the contract."""
    return float(truth_details(contract, oracle_n=oracle_n)["truth"])
