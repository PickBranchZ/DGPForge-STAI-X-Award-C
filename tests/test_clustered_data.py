from pathlib import Path

import numpy as np

from dgpforge.contracts import load_contract
from dgpforge.diagnostics import diagnostics_for_dataset
from dgpforge.estimators import run_estimators
from dgpforge.monte_carlo import run_monte_carlo
from dgpforge.report import generate_report
from dgpforge.simulate import cluster_outcome_sd, simulate_dataset


def _contract():
    return load_contract("examples/clustered_ate_icc.yaml")


def test_clustered_simulation_creates_expected_clusters_and_sizes():
    contract = _contract()
    data = simulate_dataset(contract, n=2000, seed=123)
    sizes = data.groupby("cluster_id").size()

    assert sizes.size == 50
    assert sizes.min() == 40
    assert sizes.max() == 40
    assert "Z_cluster" in data


def test_icc_calibration_produces_expected_random_effect_sd():
    contract = _contract()
    expected = np.sqrt(0.10 * contract.outcome.noise_sd**2 / 0.90)

    assert np.isclose(cluster_outcome_sd(contract), expected)


def test_empirical_icc_is_finite_and_cluster_diagnostics_present():
    contract = _contract()
    data = simulate_dataset(contract, n=2000, seed=234)
    diagnostics = diagnostics_for_dataset(data, contract)

    assert diagnostics["n_clusters"] == 50
    assert np.isfinite(diagnostics["empirical_icc"])
    assert diagnostics["few_clusters_warning"] is False


def test_cluster_robust_estimator_runs_and_returns_finite_estimate():
    contract = _contract()
    data = simulate_dataset(contract, n=2000, seed=345)
    estimates = run_estimators(data, contract)

    assert {
        "adjusted_ols_naive_se",
        "adjusted_ols_cluster_robust",
    }.issubset(set(estimates["estimator"]))
    assert np.isfinite(estimates["estimate"]).all()
    assert np.isfinite(
        estimates.loc[estimates["estimator"] == "adjusted_ols_cluster_robust", "se"]
    ).all()


def test_clustered_report_generation_creates_report(workspace_tmp_path: Path):
    contract = _contract().model_copy(update={"n_replications": 3})
    result = run_monte_carlo(contract)
    report_path = generate_report(
        contract,
        result,
        workspace_tmp_path,
        command="dgpforge run --config examples/clustered_ate_icc.yaml --out tmp",
    )
    html = report_path.read_text(encoding="utf-8")

    assert report_path.exists()
    assert "Clustered / Multilevel Structure" in html
    assert "cluster-robust SEs" in html
