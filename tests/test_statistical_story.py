from pathlib import Path

from dgpforge.contracts import load_contract
from dgpforge.monte_carlo import run_monte_carlo


ROOT = Path(__file__).resolve().parents[1]


def test_observed_confounding_story_matches_expected_bias_pattern():
    contract = load_contract(ROOT / "examples" / "causal_ate_observed_confounding.yaml")
    contract = contract.model_copy(update={"sample_sizes": [500], "n_replications": 30})
    result = run_monte_carlo(contract)
    summary = result.summary.set_index("estimator")

    naive_bias = abs(summary.loc["naive_difference", "bias"])
    adjusted_bias = abs(summary.loc["adjusted_ols", "bias"])
    aipw_bias = abs(summary.loc["aipw", "bias"])

    assert naive_bias > 0.35
    assert adjusted_bias < 0.20
    assert aipw_bias < 0.25
