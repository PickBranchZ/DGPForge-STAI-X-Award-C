from pathlib import Path

import numpy as np

from dgpforge.contracts import load_contract
from dgpforge.estimators import run_estimators
from dgpforge.monte_carlo import run_monte_carlo
from dgpforge.report import generate_report
from dgpforge.schema import DGPContract
from dgpforge.simulate import simulate_dataset
from dgpforge.truth import truth_details


def _contract():
    return load_contract("examples/missing_data_mechanisms.yaml")


def _with_missing(contract, missing: dict) -> DGPContract:
    data = contract.model_dump(mode="json")
    data["missing_data"] = missing
    return DGPContract.model_validate(data)


def test_mcar_creates_approximate_requested_missingness_rate():
    base = _contract()
    contract = _with_missing(
        base,
        {
            "enabled": True,
            "target": "Y",
            "mechanism": "MCAR",
            "rate": 0.30,
            "apply_to": ["Y"],
            "missing_indicator_prefix": "R",
        },
    )
    data = simulate_dataset(contract, n=4000, seed=123)
    missing_rate = 1.0 - data["R_Y"].mean()

    assert abs(missing_rate - 0.30) < 0.03


def test_mar_missingness_depends_on_observed_variable_direction():
    data = simulate_dataset(_contract(), n=5000, seed=234)
    high_x1 = data["X1"] > data["X1"].median()
    high_missing = 1.0 - data.loc[high_x1, "R_Y"].mean()
    low_missing = 1.0 - data.loc[~high_x1, "R_Y"].mean()

    assert high_missing > low_missing


def test_missingness_preserves_full_data_truth_and_full_outcome():
    contract = _contract()
    no_missing_data = contract.model_dump(mode="json")
    no_missing_data["missing_data"] = {"enabled": False}
    no_missing_data["estimators"] = ["naive_difference", "adjusted_ols", "aipw"]
    no_missing = DGPContract.model_validate(no_missing_data)

    observed = simulate_dataset(contract, n=500, seed=345)
    assert "Y_full" in observed
    assert observed["Y"].isna().any()
    assert observed["Y_full"].notna().all()
    assert truth_details(contract)["truth"] == truth_details(no_missing)["truth"]


def test_complete_case_and_missingness_ipw_estimators_run():
    contract = _contract()
    data = simulate_dataset(contract, n=900, seed=456)
    estimates = run_estimators(data, contract)

    assert {
        "adjusted_ols_complete_case",
        "aipw_complete_case",
        "adjusted_ols_missingness_ipw",
    }.issubset(set(estimates["estimator"]))
    assert np.isfinite(estimates["estimate"]).all()


def test_missing_data_report_generation_creates_report(workspace_tmp_path: Path):
    contract = _contract().model_copy(update={"sample_sizes": [300], "n_replications": 3})
    result = run_monte_carlo(contract)
    report_path = generate_report(
        contract,
        result,
        workspace_tmp_path,
        command="dgpforge run --config examples/missing_data_mechanisms.yaml --out tmp",
    )
    html = report_path.read_text(encoding="utf-8")

    assert report_path.exists()
    assert "Missing Data Mechanism" in html
    assert "full-data truth remains the benchmark target" in html
