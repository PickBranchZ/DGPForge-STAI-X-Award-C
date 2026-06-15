from pathlib import Path

from dgpforge.cli import main
from dgpforge.contracts import load_contract, save_contract


ROOT = Path(__file__).resolve().parents[1]


def test_cli_smoke_creates_report(workspace_tmp_path):
    contract = load_contract(ROOT / "examples" / "causal_ate_observed_confounding.yaml")
    contract = contract.model_copy(update={"sample_sizes": [120], "n_replications": 3})
    config_path = workspace_tmp_path / "smoke.yaml"
    save_contract(contract, config_path)

    out_dir = workspace_tmp_path / "report"
    main(["run", "--config", str(config_path), "--out", str(out_dir)])
    assert (out_dir / "report.html").exists()
    assert (out_dir / "contract.yaml").read_text(encoding="utf-8") == config_path.read_text(
        encoding="utf-8"
    )
    reproduce_text = (out_dir / "reproduce.md").read_text(encoding="utf-8")
    assert "dgpforge run --config contract.yaml --out ." in reproduce_text
    assert "MCSE bias" in (out_dir / "report.html").read_text(encoding="utf-8")


def test_cli_grid_smoke_creates_report(workspace_tmp_path):
    config_path = workspace_tmp_path / "grid.yaml"
    config_path.write_text(
        "\n".join(
            [
                "name: cli_grid",
                f"base_config: \"{(ROOT / 'examples' / 'causal_ate_observed_confounding.yaml').as_posix()}\"",
                "sample_sizes: [80]",
                "n_replications: 2",
                "seed: 20260602",
                "confounding_strengths: [0.0]",
                "heterogeneity_coefficients: [0.0]",
                "estimators:",
                "  - naive_difference",
                "  - aipw",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = workspace_tmp_path / "grid_report"
    main(["grid", "--config", str(config_path), "--out", str(out_dir)])
    assert (out_dir / "report.html").exists()
    assert (out_dir / "grid_results.csv").exists()


def test_cli_sensitivity_smoke_creates_report(workspace_tmp_path):
    config_path = workspace_tmp_path / "sensitivity.yaml"
    config_path.write_text(
        "\n".join(
            [
                "name: cli_sensitivity",
                f"base_config: \"{(ROOT / 'examples' / 'causal_binary_outcome.yaml').as_posix()}\"",
                "sample_size: 80",
                "n_replications: 2",
                "seed: 20260602",
                "U_to_treatment_strength: [0.0]",
                "U_to_outcome_strength: [0.0]",
                "estimators:",
                "  - aipw_risk_difference",
                "  - adjusted_oracle_includes_U",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = workspace_tmp_path / "sensitivity_report"
    main(["sensitivity", "--config", str(config_path), "--out", str(out_dir)])
    assert (out_dir / "report.html").exists()
    assert (out_dir / "sensitivity_summary.csv").exists()
