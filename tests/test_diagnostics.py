from pathlib import Path

from dgpforge.contracts import load_contract
from dgpforge.diagnostics import diagnostics_for_dataset
from dgpforge.monte_carlo import run_monte_carlo
from dgpforge.simulate import simulate_dataset


ROOT = Path(__file__).resolve().parents[1]


def test_weak_overlap_config_triggers_positivity_warning():
    contract = load_contract(ROOT / "examples" / "causal_ate_weak_overlap.yaml")
    data = simulate_dataset(contract, n=2500, seed=456)
    diagnostics = diagnostics_for_dataset(data, contract)
    assert diagnostics["positivity_warning"] is True


def test_randomized_constant_propensity_does_not_trigger_positivity_warning():
    contract = load_contract(ROOT / "examples" / "causal_ate_randomized.yaml")
    data = simulate_dataset(contract, n=1200, seed=456)
    diagnostics = diagnostics_for_dataset(data, contract)
    assert diagnostics["positivity_warning"] is False


def test_diagnostics_summary_excludes_replication_metadata():
    contract = load_contract(ROOT / "examples" / "causal_ate_observed_confounding.yaml")
    contract = contract.model_copy(update={"sample_sizes": [120], "n_replications": 3})
    result = run_monte_carlo(contract)

    assert "replication" not in result.diagnostics.columns
    assert "seed" not in result.diagnostics.columns
