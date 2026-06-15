from pathlib import Path

from dgpforge.contracts import load_contract
from dgpforge.truth import analytical_ate


ROOT = Path(__file__).resolve().parents[1]


def test_constant_effect_truth_equals_configured_treatment_effect():
    contract = load_contract(ROOT / "examples" / "causal_ate_observed_confounding.yaml")
    assert analytical_ate(contract) == contract.outcome.treatment_effect


def test_supported_heterogeneous_effect_truth_uses_modifier_mean():
    contract = load_contract(ROOT / "examples" / "causal_ate_observed_confounding.yaml")
    contract.outcome.treatment_effect_heterogeneity.enabled = True
    contract.outcome.treatment_effect_heterogeneity.modifier = "X2"
    contract.outcome.treatment_effect_heterogeneity.coefficient = 0.5

    assert analytical_ate(contract) == 2.2


def test_heterogeneous_effect_example_truth_matches_configured_modifier_mean():
    contract = load_contract(ROOT / "examples" / "causal_ate_heterogeneous_effect.yaml")
    assert analytical_ate(contract) == 2.2
