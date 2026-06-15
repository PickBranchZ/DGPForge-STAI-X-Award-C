from pathlib import Path

import numpy as np

from dgpforge.contracts import load_contract
from dgpforge.estimators import _covariate_names
from dgpforge.schema import UnobservedConfounderSpec
from dgpforge.sensitivity import run_sensitivity_grid
from dgpforge.simulate import simulate_dataset


ROOT = Path(__file__).resolve().parents[1]


def test_unobserved_confounder_affects_treatment_and_outcome_when_enabled():
    contract = load_contract(ROOT / "examples" / "causal_binary_outcome.yaml")
    contract = contract.model_copy(
        update={
            "unobserved_confounder": UnobservedConfounderSpec(
                enabled=True,
                name="U",
                treatment_coefficient=1.0,
                outcome_coefficient=1.0,
                observed=False,
            )
        }
    )
    data = simulate_dataset(contract, n=2000, seed=789)

    assert "U" in data.columns
    assert abs(np.corrcoef(data["U"], data["A"])[0, 1]) > 0.15
    assert abs(np.corrcoef(data["U"], data["p0"])[0, 1]) > 0.15


def test_estimators_exclude_hidden_u_by_default():
    contract = load_contract(ROOT / "examples" / "causal_binary_outcome.yaml")
    hidden = contract.model_copy(
        update={
            "unobserved_confounder": UnobservedConfounderSpec(
                enabled=True,
                name="U",
                treatment_coefficient=1.0,
                outcome_coefficient=1.0,
                observed=False,
            )
        }
    )
    observed = hidden.model_copy(
        update={
            "unobserved_confounder": hidden.unobserved_confounder.model_copy(
                update={"observed": True}
            )
        }
    )

    assert "U" not in _covariate_names(hidden)
    assert "U" in _covariate_names(observed)
    assert "U" in _covariate_names(hidden, include_unobserved=True)


def test_sensitivity_grid_writes_summary_and_report(workspace_tmp_path):
    config_path = workspace_tmp_path / "mini_sensitivity.yaml"
    config_path.write_text(
        "\n".join(
            [
                "name: mini_sensitivity",
                f"base_config: \"{(ROOT / 'examples' / 'causal_binary_outcome.yaml').as_posix()}\"",
                "sample_size: 120",
                "n_replications: 2",
                "seed: 20260602",
                "U_to_treatment_strength: [0.0, 1.0]",
                "U_to_outcome_strength: [0.0, 1.0]",
                "estimators:",
                "  - naive_risk_difference",
                "  - aipw_risk_difference",
                "  - adjusted_oracle_includes_U",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report_path = run_sensitivity_grid(config_path, workspace_tmp_path / "out")

    assert report_path.exists()
    assert (workspace_tmp_path / "out" / "sensitivity_summary.csv").exists()
    assert (workspace_tmp_path / "out" / "sensitivity_grid.csv").exists()
