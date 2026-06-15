from pathlib import Path

import numpy as np

from dgpforge.contracts import load_contract
from dgpforge.estimators import run_estimators
from dgpforge.monte_carlo import run_monte_carlo
from dgpforge.report import generate_report
from dgpforge.simulate import simulate_dataset
from dgpforge.truth import truth_details


def _contract():
    return load_contract("examples/causal_count_rate_outcome.yaml")


def test_count_simulation_outputs_integer_counts_and_positive_exposure():
    contract = _contract()
    data = simulate_dataset(contract, n=300, seed=123)

    assert (data["exposure"] > 0).all()
    assert (data[["mu0", "mu1", "rate0", "rate1"]] > 0).all().all()
    assert (data[["Y", "Y0", "Y1"]] >= 0).all().all()
    assert np.allclose(data[["Y", "Y0", "Y1"]] % 1, 0)


def test_count_truth_has_finite_rate_estimands():
    details = truth_details(_contract(), oracle_n=5000)

    assert np.isfinite(details["true_rate_0"])
    assert np.isfinite(details["true_rate_1"])
    assert np.isfinite(details["true_rate_difference"])
    assert details["true_rate_ratio"] > 0
    assert np.isfinite(details["true_log_rate_ratio"])


def test_count_rate_estimators_return_finite_point_estimates():
    contract = _contract()
    data = simulate_dataset(contract, n=800, seed=456)
    estimates = run_estimators(data, contract)

    assert {
        "naive_rate_difference",
        "poisson_offset_gcomp_rate_difference",
        "ipw_rate_difference",
    }.issubset(set(estimates["estimator"]))
    assert np.isfinite(estimates["estimate"]).all()
    naive = estimates[estimates["estimator"] == "naive_rate_difference"].iloc[0]
    offset = estimates[estimates["estimator"] == "poisson_offset_gcomp_rate_difference"].iloc[0]
    ipw = estimates[estimates["estimator"] == "ipw_rate_difference"].iloc[0]
    assert np.isfinite(naive["se"])
    assert np.isfinite(naive["ci_lower"])
    assert np.isfinite(naive["ci_upper"])
    assert np.isnan(offset["se"])
    assert np.isnan(ipw["se"])


def test_count_report_generation_creates_report(workspace_tmp_path: Path):
    contract = _contract().model_copy(update={"sample_sizes": [300], "n_replications": 3})
    result = run_monte_carlo(contract, oracle_n=5000)
    report_path = generate_report(
        contract,
        result,
        workspace_tmp_path,
        command="dgpforge run --config examples/causal_count_rate_outcome.yaml --out tmp",
    )
    html = report_path.read_text(encoding="utf-8")

    assert report_path.exists()
    assert "Count/Rate Outcome With Exposure Offset" in html
    assert (
        "Count/rate SE/CI are reported only when an implemented approximation is available" in html
    )
