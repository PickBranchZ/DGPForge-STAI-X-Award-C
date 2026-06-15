from pathlib import Path

from dgpforge.contracts import load_contract
from dgpforge.monte_carlo import run_monte_carlo


ROOT = Path(__file__).resolve().parents[1]


def test_randomized_treatment_makes_naive_estimator_approximately_unbiased():
    contract = load_contract(ROOT / "examples" / "causal_ate_randomized.yaml")
    contract = contract.model_copy(update={"sample_sizes": [350], "n_replications": 24})
    result = run_monte_carlo(contract)
    naive = result.summary[result.summary["estimator"] == "naive_difference"].iloc[0]
    assert abs(naive["bias"]) < 0.30
