from pathlib import Path

import numpy as np
import yaml

from dgpforge.contracts import load_contract
from dgpforge.estimators import (
    _default_omit_confounder,
    _default_omit_outcome_features,
    run_estimators,
)
from dgpforge.schema import DGPContract
from dgpforge.simulate import simulate_dataset


ROOT = Path(__file__).resolve().parents[1]


def test_misspecification_omits_covariates_by_role_not_name():
    source = yaml.safe_load(
        (ROOT / "examples" / "causal_ate_observed_confounding.yaml").read_text()
    )
    source["covariates"] = {
        "Z1": source["covariates"]["X1"],
        "Z2": source["covariates"]["X2"],
        "X3": source["covariates"]["X3"],
    }
    source["treatment"]["formula"] = {
        "intercept": -0.2,
        "Z1": 0.8,
        "Z2": 0.6,
    }
    source["outcome"]["coefficients"] = {
        "intercept": 0.0,
        "Z1": 1.0,
        "Z2": 0.5,
        "X3": 0.5,
    }
    source["outcome"]["treatment_effect_heterogeneity"]["modifier"] = "Z1"
    contract = DGPContract.model_validate(source)

    assert _default_omit_confounder(contract) == ("Z1", "Z2")
    assert _default_omit_outcome_features(contract) == ("Z1", "Z2", "X3")


def test_double_robustness_estimators_return_finite_values():
    contract = load_contract(ROOT / "examples" / "causal_ate_double_robustness.yaml")
    data = simulate_dataset(contract, n=600, seed=12345)
    estimates = run_estimators(data, contract)

    expected = {
        "aipw",
        "aipw_ps_misspecified",
        "aipw_outcome_misspecified",
        "aipw_double_misspecified",
    }
    rows = estimates[estimates["estimator"].isin(expected)]

    assert set(rows["estimator"]) == expected
    assert np.isfinite(rows["estimate"]).all()
    assert np.isfinite(rows["se"]).all()
