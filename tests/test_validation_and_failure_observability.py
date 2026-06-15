from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from dgpforge import estimators
from dgpforge.contracts import load_contract
from dgpforge.schema import DGPContract
from dgpforge.simulate import simulate_dataset


def _continuous_contract_data(estimator: str) -> dict[str, object]:
    return {
        "name": "validation_continuous",
        "template": "cross_sectional_binary_treatment_continuous_outcome",
        "sample_sizes": [50],
        "n_replications": 2,
        "seed": 7,
        "covariates": {
            "X1": {
                "type": "continuous",
                "distribution": "normal",
                "mean": 0,
                "sd": 1,
                "role": "confounder",
            }
        },
        "treatment": {
            "name": "A",
            "type": "binary",
            "assignment": "logistic",
            "formula": {"intercept": 0.0, "X1": 0.4},
        },
        "outcome": {
            "name": "Y",
            "type": "continuous",
            "model": "linear",
            "treatment_effect": 1.0,
            "coefficients": {"intercept": 0.0, "X1": 0.5},
            "noise_sd": 1.0,
        },
        "estimand": {"name": "marginal_ATE", "contrast": "E[Y(1) - Y(0)]"},
        "estimators": [estimator],
    }


def _binary_contract_data(estimator: str) -> dict[str, object]:
    data = _continuous_contract_data(estimator)
    data["name"] = "validation_binary"
    data["template"] = "cross_sectional_binary_treatment_binary_outcome"
    data["outcome"] = {
        "name": "Y",
        "type": "binary",
        "model": "logistic",
        "treatment_effect": 0.6,
        "coefficients": {"intercept": -1.0, "X1": 0.5},
        "noise_sd": None,
    }
    data["estimand"] = {
        "name": "marginal_risk_difference",
        "contrast": "E[Y(1)] - E[Y(0)]",
        "primary": "risk_difference",
    }
    return data


def _count_contract_data(estimator: str) -> dict[str, object]:
    data = _continuous_contract_data(estimator)
    data["name"] = "validation_count"
    data["template"] = "cross_sectional_binary_treatment_count_outcome"
    data["outcome"] = {
        "name": "Y",
        "type": "count",
        "model": "poisson",
        "treatment_effect": 0.4,
        "coefficients": {"intercept": -1.0, "X1": 0.2},
        "noise_sd": None,
        "exposure": {"name": "exposure", "meanlog": 1.0, "sdlog": 0.2, "scale": 1.0},
    }
    data["estimand"] = {
        "name": "marginal_rate_difference",
        "contrast": "rate[Y(1)] - rate[Y(0)]",
        "primary": "rate_difference",
    }
    return data


def test_continuous_contract_rejects_binary_estimator() -> None:
    with pytest.raises(ValidationError, match="incompatible with outcome.type='continuous'"):
        DGPContract.model_validate(_continuous_contract_data("aipw_risk_difference"))


def test_binary_contract_rejects_continuous_estimator() -> None:
    with pytest.raises(ValidationError, match="incompatible with outcome.type='binary'"):
        DGPContract.model_validate(_binary_contract_data("adjusted_ols"))


def test_count_contract_rejects_binary_estimator() -> None:
    with pytest.raises(ValidationError, match="incompatible with outcome.type='count'"):
        DGPContract.model_validate(_count_contract_data("aipw_risk_difference"))


def test_missingness_ipw_requires_missing_data() -> None:
    with pytest.raises(ValidationError, match="requires missing_data.enabled=True"):
        DGPContract.model_validate(_continuous_contract_data("adjusted_ols_missingness_ipw"))


def test_cluster_robust_estimator_requires_clusters() -> None:
    with pytest.raises(ValidationError, match="requires clusters.enabled=True"):
        DGPContract.model_validate(_continuous_contract_data("adjusted_ols_cluster_robust"))


def test_oracle_estimator_requires_latent_u() -> None:
    with pytest.raises(ValidationError, match="requires unobserved_confounder.enabled=True"):
        DGPContract.model_validate(_continuous_contract_data("adjusted_oracle_includes_U"))


def test_example_yaml_contracts_still_validate() -> None:
    for path in Path("examples").glob("*.yaml"):
        if path.name == "calibration_targets.yaml":
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if "template" not in data:
            continue
        load_contract(path)


def test_run_estimators_records_unexpected_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    contract = DGPContract.model_validate(_continuous_contract_data("naive_difference"))
    data = simulate_dataset(contract, n=30, seed=11)

    def broken_estimator(*_args: object, **_kwargs: object) -> estimators.EstimatorResult:
        raise RuntimeError("synthetic estimator failure")

    monkeypatch.setitem(estimators.ESTIMATORS, "naive_difference", broken_estimator)

    results = estimators.run_estimators(data, contract)

    assert results.loc[0, "status"] == "failed"
    assert results.loc[0, "error_type"] == "RuntimeError"
    assert "synthetic estimator failure" in results.loc[0, "error_message"]
    assert results.loc[0, "estimate"] != results.loc[0, "estimate"]
