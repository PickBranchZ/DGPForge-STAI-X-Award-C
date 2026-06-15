from pathlib import Path

from dgpforge.contracts import load_contract
from dgpforge.diagnostics import diagnostics_for_dataset
from dgpforge.simulate import simulate_dataset


ROOT = Path(__file__).resolve().parents[1]


def test_same_seed_gives_reproducible_simulation_summary():
    contract = load_contract(ROOT / "examples" / "causal_ate_observed_confounding.yaml")
    first = simulate_dataset(contract, n=300, seed=123)
    second = simulate_dataset(contract, n=300, seed=123)

    first_summary = diagnostics_for_dataset(first, contract)
    second_summary = diagnostics_for_dataset(second, contract)
    assert first_summary["treatment_prevalence"] == second_summary["treatment_prevalence"]
    assert first["Y"].mean() == second["Y"].mean()
