from pathlib import Path

import pandas as pd

from dgpforge.grid import run_scenario_grid


ROOT = Path(__file__).resolve().parents[1]


def test_scenario_grid_writes_combined_report_and_csvs(workspace_tmp_path):
    config_path = workspace_tmp_path / "mini_grid.yaml"
    config_path.write_text(
        "\n".join(
            [
                "name: test_grid",
                f"base_config: \"{(ROOT / 'examples' / 'causal_ate_observed_confounding.yaml').as_posix()}\"",
                "sample_sizes: [80]",
                "n_replications: 2",
                "seed: 20260602",
                "confounding_strengths: [0.0, 1.5]",
                "heterogeneity_coefficients: [0.0]",
                "heterogeneity_modifier: X2",
                "estimators:",
                "  - naive_difference",
                "  - aipw",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = workspace_tmp_path / "grid"
    report_path = run_scenario_grid(config_path, out_dir)

    assert report_path.exists()
    assert (out_dir / "grid_results.csv").exists()
    assert (out_dir / "scenario_summary.csv").exists()
    assert len(pd.read_csv(out_dir / "scenario_summary.csv")) == 2
