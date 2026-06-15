from pathlib import Path

import numpy as np

from dgpforge.contracts import load_contract
from dgpforge.estimators import run_estimators
from dgpforge.monte_carlo import run_monte_carlo
from dgpforge.report import generate_report
from dgpforge.simulate import simulate_dataset
from dgpforge.truth import truth_details


ROOT = Path(__file__).resolve().parents[1]


def test_binary_outcome_simulation_has_binary_potential_outcomes_and_probabilities():
    contract = load_contract(ROOT / "examples" / "causal_binary_outcome.yaml")
    data = simulate_dataset(contract, n=300, seed=123)

    for column in ["Y", "Y0", "Y1"]:
        assert set(data[column].unique()).issubset({0.0, 1.0})
    assert data["p0"].between(0, 1).all()
    assert data["p1"].between(0, 1).all()
    assert np.isfinite(data["logit_tau"]).all()


def test_binary_truth_returns_finite_marginal_estimands():
    contract = load_contract(ROOT / "examples" / "causal_binary_outcome.yaml")
    details = truth_details(contract, oracle_n=20_000)

    assert 0 < details["true_EY0"] < 1
    assert 0 < details["true_EY1"] < 1
    assert np.isfinite(details["true_risk_difference"])
    assert details["true_risk_ratio"] > 0
    assert details["true_odds_ratio"] > 0


def test_binary_estimators_return_finite_smoke_values():
    contract = load_contract(ROOT / "examples" / "causal_binary_outcome.yaml")
    data = simulate_dataset(contract, n=600, seed=456)
    estimates = run_estimators(data, contract)

    assert np.isfinite(estimates["estimate"]).all()
    assert {"naive_risk_difference", "aipw_risk_difference"}.issubset(set(estimates["estimator"]))


def test_binary_report_generation_creates_html(workspace_tmp_path):
    contract = load_contract(ROOT / "examples" / "causal_binary_outcome.yaml")
    contract = contract.model_copy(update={"sample_sizes": [160], "n_replications": 3})
    result = run_monte_carlo(contract, oracle_n=10_000)

    report_path = generate_report(contract, result, workspace_tmp_path, command="test")

    html = report_path.read_text(encoding="utf-8")
    assert "Binary Outcome Marginal Estimands" in html
    assert "logistic treatment coefficient is a conditional model parameter" in html
