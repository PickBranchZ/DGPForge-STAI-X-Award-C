from pathlib import Path

import numpy as np
import yaml

from dgpforge.calibration import calibrate_contract, run_calibration
from dgpforge.contracts import load_contract
from dgpforge.diagnostics import diagnostics_for_dataset
from dgpforge.simulate import cluster_outcome_sd, simulate_dataset


def test_calibration_hits_treatment_and_binary_prevalence_targets():
    contract, summary, _ = calibrate_contract("examples/calibration_targets.yaml")
    oracle = simulate_dataset(contract, n=30000, seed=20260613)

    treatment_row = summary[summary["target"] == "treatment_prevalence"].iloc[0]
    binary_row = summary[summary["target"] == "binary_outcome_prevalence_control"].iloc[0]
    assert bool(treatment_row["passed"])
    assert bool(binary_row["passed"])
    assert abs(float(oracle["propensity"].mean()) - 0.35) < 0.015
    assert abs(float(oracle["p0"].mean()) - 0.20) < 0.015


def test_calibration_hits_count_baseline_rate(workspace_tmp_path: Path):
    config = workspace_tmp_path / "count_calibration.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "base_config": str(Path("examples/causal_count_rate_outcome.yaml").resolve()),
                "calibration": {
                    "oracle_n": 30000,
                    "seed": 20260614,
                    "targets": {"count_baseline_rate": 0.002},
                    "tolerance": {"count_baseline_rate": 0.0001},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    contract, summary, _ = calibrate_contract(config)
    oracle = simulate_dataset(contract, n=30000, seed=20260614)
    achieved = float(oracle["mu0"].sum() / oracle["exposure"].sum())

    assert bool(summary.iloc[0]["passed"])
    assert abs(achieved - 0.002) < 0.00015


def test_icc_calibration_formula_sets_expected_variance(workspace_tmp_path: Path):
    config = workspace_tmp_path / "icc_calibration.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "base_config": str(Path("examples/clustered_ate_icc.yaml").resolve()),
                "calibration": {
                    "oracle_n": 2000,
                    "seed": 20260615,
                    "targets": {"icc": 0.20},
                    "tolerance": {"icc": 0.01},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    contract, summary, _ = calibrate_contract(config)
    expected_sd = np.sqrt(0.20 * contract.outcome.noise_sd**2 / 0.80)

    assert bool(summary.iloc[0]["passed"])
    assert np.isclose(cluster_outcome_sd(contract), expected_sd)


def test_run_calibration_writes_loadable_outputs(workspace_tmp_path: Path):
    report_path = run_calibration("examples/calibration_targets.yaml", workspace_tmp_path)
    calibrated_path = workspace_tmp_path / "calibrated_dgp.yaml"
    summary_path = workspace_tmp_path / "calibration_summary.csv"
    contract = load_contract(calibrated_path)
    data = simulate_dataset(contract, n=1000, seed=99)
    diagnostics = diagnostics_for_dataset(data, contract)

    assert report_path.exists()
    assert calibrated_path.exists()
    assert summary_path.exists()
    assert diagnostics["treatment_prevalence"] > 0
