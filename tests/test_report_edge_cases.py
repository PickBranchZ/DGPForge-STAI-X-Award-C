from pathlib import Path

import yaml

from dgpforge.contracts import load_contract
from dgpforge.monte_carlo import run_monte_carlo
from dgpforge.report import generate_report
from dgpforge.schema import DGPContract
from dgpforge.sensitivity import run_sensitivity_grid


ROOT = Path(__file__).resolve().parents[1]


def test_continuous_report_handles_null_noise_sd(workspace_tmp_path: Path):
    data = load_contract(ROOT / "examples" / "causal_ate_observed_confounding.yaml").model_dump(
        mode="json"
    )
    data["sample_sizes"] = [120]
    data["n_replications"] = 2
    data["outcome"]["noise_sd"] = None
    contract = DGPContract.model_validate(data)

    result = run_monte_carlo(contract)
    report_path = generate_report(
        contract,
        result,
        workspace_tmp_path,
        command="dgpforge run --config null_noise.yaml --out tmp",
    )

    html = report_path.read_text(encoding="utf-8")
    assert "noise SD 1" in html


def test_sensitivity_heatmap_handles_non_default_estimator_set(workspace_tmp_path: Path):
    config = {
        "base_config": (ROOT / "examples" / "causal_binary_outcome.yaml").as_posix(),
        "sample_size": 80,
        "n_replications": 2,
        "seed": 123,
        "U_to_treatment_strength": [0.0],
        "U_to_outcome_strength": [0.0],
        "estimators": ["naive_risk_difference"],
    }
    config_path = workspace_tmp_path / "mini_sensitivity.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    report_path = run_sensitivity_grid(config_path, workspace_tmp_path / "out")

    assert report_path.exists()
    assert (workspace_tmp_path / "out" / "sensitivity_bias_heatmap.png").exists()
    assert (workspace_tmp_path / "out" / "sensitivity_grid.csv").exists()
