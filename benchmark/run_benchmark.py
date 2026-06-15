"""Small seeded benchmark for the DGPForge Award C demo."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import shutil
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TEMP_ROOT = ROOT / "benchmark_tmp"

from dgpforge.calibration import run_calibration
from dgpforge.contracts import load_contract
from dgpforge.grid import run_scenario_grid
from dgpforge.monte_carlo import run_monte_carlo
from dgpforge.report import generate_report
from dgpforge.sensitivity import run_sensitivity_grid
from dgpforge.simulate import simulate_dataset


@dataclass(frozen=True)
class BenchmarkCheck:
    name: str
    passed: bool
    detail: str


_TEMP_INDEX = 0


@contextmanager
def _temp_dir():
    global _TEMP_INDEX
    TEMP_ROOT.mkdir(exist_ok=True)
    path = TEMP_ROOT / f"run_{_TEMP_INDEX}"
    _TEMP_INDEX += 1
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _small_contract(path: str, sample_size: int = 500, reps: int = 30):
    contract = load_contract(ROOT / path)
    return contract.model_copy(update={"sample_sizes": [sample_size], "n_replications": reps})


def _bias(result, estimator: str) -> float:
    row = result.summary[result.summary["estimator"] == estimator].iloc[0]
    return float(row["bias"])


def _summary_value(result, estimator: str, column: str) -> float:
    row = result.summary[result.summary["estimator"] == estimator].iloc[0]
    return float(row[column])


def run_checks() -> list[BenchmarkCheck]:
    checks: list[BenchmarkCheck] = []

    randomized = run_monte_carlo(_small_contract("examples/causal_ate_randomized.yaml"))
    randomized_naive = abs(_bias(randomized, "naive_difference"))
    checks.append(
        BenchmarkCheck(
            "randomized naive approximately unbiased",
            randomized_naive < 0.30,
            f"|bias|={randomized_naive:.3f}",
        )
    )

    observed_contract = _small_contract("examples/causal_ate_observed_confounding.yaml")
    observed = run_monte_carlo(observed_contract)
    naive = abs(_bias(observed, "naive_difference"))
    adjusted = abs(_bias(observed, "adjusted_ols"))
    aipw = abs(_bias(observed, "aipw"))
    checks.append(
        BenchmarkCheck(
            "observed confounding biases naive estimator", naive > 0.35, f"|bias|={naive:.3f}"
        )
    )
    checks.append(
        BenchmarkCheck("adjusted OLS close to known ATE", adjusted < 0.20, f"|bias|={adjusted:.3f}")
    )
    checks.append(BenchmarkCheck("AIPW close to known ATE", aipw < 0.25, f"|bias|={aipw:.3f}"))
    mcse_columns = {
        "mcse_bias",
        "mcse_rmse",
        "mcse_coverage",
        "n_attempted",
        "n_valid",
        "failure_rate",
    }
    checks.append(
        BenchmarkCheck(
            "Monte Carlo precision columns present",
            mcse_columns.issubset(set(observed.summary.columns)),
            ", ".join(sorted(mcse_columns)),
        )
    )
    checks.append(
        BenchmarkCheck(
            "summary keeps attempted denominator",
            int(observed.summary["n_attempted"].min()) == observed_contract.n_replications,
            f"min attempted={int(observed.summary['n_attempted'].min())}",
        )
    )

    heterogeneous = run_monte_carlo(
        _small_contract("examples/causal_ate_heterogeneous_effect.yaml", sample_size=600, reps=20)
    )
    checks.append(
        BenchmarkCheck(
            "heterogeneous-effect true ATE is analytical",
            abs(heterogeneous.truth - 2.2) < 0.01,
            f"truth={heterogeneous.truth:.3f}",
        )
    )

    weak = run_monte_carlo(
        _small_contract("examples/causal_ate_weak_overlap.yaml", sample_size=800, reps=8)
    )
    weak_warning = bool(weak.diagnostics["positivity_warning"].any())
    checks.append(
        BenchmarkCheck(
            "weak overlap warning triggered",
            weak_warning,
            str(weak.diagnostics["positivity_message"].iloc[0]),
        )
    )

    dr = run_monte_carlo(
        _small_contract("examples/causal_ate_double_robustness.yaml", sample_size=1000, reps=45)
    )
    aipw_bias = abs(_bias(dr, "aipw"))
    ps_wrong = abs(_bias(dr, "aipw_ps_misspecified"))
    outcome_wrong = abs(_bias(dr, "aipw_outcome_misspecified"))
    double_wrong = abs(_bias(dr, "aipw_double_misspecified"))
    checks.append(
        BenchmarkCheck(
            "AIPW main variant close in DR demo",
            aipw_bias < 0.35,
            f"|bias|={aipw_bias:.3f}",
        )
    )
    checks.append(
        BenchmarkCheck(
            "one-correct AIPW variants beat double-misspecified variant",
            max(ps_wrong, outcome_wrong) < double_wrong,
            f"ps_wrong={ps_wrong:.3f}, outcome_wrong={outcome_wrong:.3f}, double_wrong={double_wrong:.3f}",
        )
    )
    checks.append(
        BenchmarkCheck(
            "coverage MCSE is finite",
            _summary_value(dr, "aipw", "mcse_coverage") >= 0,
            f"mcse_coverage={_summary_value(dr, 'aipw', 'mcse_coverage'):.3f}",
        )
    )

    binary_contract = _small_contract(
        "examples/causal_binary_outcome.yaml", sample_size=700, reps=24
    )
    binary = run_monte_carlo(binary_contract)
    details = binary.truth_details
    finite_binary_truth = (
        0 < float(details["true_EY0"]) < 1
        and 0 < float(details["true_EY1"]) < 1
        and float(details["true_risk_ratio"]) > 0
        and float(details["true_odds_ratio"]) > 0
    )
    checks.append(
        BenchmarkCheck(
            "binary truth has finite marginal risks and ratios",
            finite_binary_truth,
            f"EY1={float(details['true_EY1']):.3f}, EY0={float(details['true_EY0']):.3f}, RD={binary.truth:.3f}",
        )
    )
    binary_aipw_bias = abs(_bias(binary, "aipw_risk_difference"))
    checks.append(
        BenchmarkCheck(
            "binary AIPW risk difference close to known RD",
            binary_aipw_bias < 0.12,
            f"|bias|={binary_aipw_bias:.3f}",
        )
    )
    checks.append(
        BenchmarkCheck(
            "binary summary includes MCSE columns",
            mcse_columns.issubset(set(binary.summary.columns)),
            ", ".join(sorted(mcse_columns)),
        )
    )

    with _temp_dir() as temp_dir:
        report_path = generate_report(
            observed_contract,
            observed,
            out_dir=temp_dir,
            command="python benchmark/run_benchmark.py",
        )
        checks.append(
            BenchmarkCheck(
                "report generation works", report_path.exists(), "temporary report rendered"
            )
        )

    with _temp_dir() as temp_dir:
        binary_report = generate_report(
            binary_contract,
            binary,
            out_dir=temp_dir,
            command="python benchmark/run_benchmark.py",
        )
        html = binary_report.read_text(encoding="utf-8")
        checks.append(
            BenchmarkCheck(
                "binary outcome report generation works",
                binary_report.exists() and "Binary Outcome Marginal Estimands" in html,
                "temporary binary report rendered",
            )
        )

    count_contract = _small_contract(
        "examples/causal_count_rate_outcome.yaml", sample_size=500, reps=10
    )
    count = run_monte_carlo(count_contract, oracle_n=20_000)
    count_truth_finite = (
        count.truth > 0
        and float(count.truth_details["true_rate_0"]) > 0
        and float(count.truth_details["true_rate_ratio"]) > 0
    )
    checks.append(
        BenchmarkCheck(
            "count/rate truth finite",
            count_truth_finite,
            f"rate0={float(count.truth_details['true_rate_0']):.4f}, RD={count.truth:.4f}",
        )
    )
    count_gcomp_bias = abs(_bias(count, "poisson_offset_gcomp_rate_difference"))
    checks.append(
        BenchmarkCheck(
            "count/rate offset g-comp close to known rate difference",
            count_gcomp_bias < 0.0003,
            f"|bias|={count_gcomp_bias:.5f}",
        )
    )
    with _temp_dir() as temp_dir:
        count_report = generate_report(
            count_contract,
            count,
            out_dir=temp_dir,
            command="python benchmark/run_benchmark.py",
        )
        html = count_report.read_text(encoding="utf-8")
        checks.append(
            BenchmarkCheck(
                "count/rate report generation works",
                count_report.exists() and "Count/Rate Outcome With Exposure Offset" in html,
                "temporary count/rate report rendered",
            )
        )

    missing_contract = _small_contract(
        "examples/missing_data_mechanisms.yaml", sample_size=600, reps=12
    )
    missing = run_monte_carlo(missing_contract)
    missing_data = simulate_dataset(missing_contract, n=1500, seed=20260611)
    missing_rate = float(1.0 - missing_data["R_Y"].mean())
    checks.append(
        BenchmarkCheck(
            "missingness rate achieved",
            abs(missing_rate - missing_contract.missing_data.rate) < 0.04,
            f"missing_rate={missing_rate:.3f}",
        )
    )
    checks.append(
        BenchmarkCheck(
            "missing data preserves full-data truth",
            "Y_full" in missing_data and missing_data["Y"].isna().any(),
            "Y_full exists and observed Y is masked",
        )
    )
    with _temp_dir() as temp_dir:
        missing_report = generate_report(
            missing_contract,
            missing,
            out_dir=temp_dir,
            command="python benchmark/run_benchmark.py",
        )
        html = missing_report.read_text(encoding="utf-8")
        checks.append(
            BenchmarkCheck(
                "missing data report generation works",
                missing_report.exists() and "Missing Data Mechanism" in html,
                "temporary missing-data report rendered",
            )
        )

    clustered_contract = _small_contract(
        "examples/clustered_ate_icc.yaml", sample_size=2000, reps=16
    )
    clustered = run_monte_carlo(clustered_contract)
    cluster_se = _summary_value(clustered, "adjusted_ols_cluster_robust", "mean_estimated_se")
    naive_se = _summary_value(clustered, "adjusted_ols_naive_se", "mean_estimated_se")
    checks.append(
        BenchmarkCheck(
            "cluster-robust estimator runs",
            cluster_se > 0 and naive_se > 0,
            f"naive_se={naive_se:.3f}, cluster_se={cluster_se:.3f}",
        )
    )
    checks.append(
        BenchmarkCheck(
            "cluster diagnostics include ICC",
            float(clustered.diagnostics["n_clusters"].iloc[0]) == 50
            and pd.notna(clustered.diagnostics["empirical_icc"].iloc[0]),
            f"empirical_icc={float(clustered.diagnostics['empirical_icc'].iloc[0]):.3f}",
        )
    )
    with _temp_dir() as temp_dir:
        clustered_report = generate_report(
            clustered_contract,
            clustered,
            out_dir=temp_dir,
            command="python benchmark/run_benchmark.py",
        )
        html = clustered_report.read_text(encoding="utf-8")
        checks.append(
            BenchmarkCheck(
                "clustered ICC report generation works",
                clustered_report.exists() and "Clustered / Multilevel Structure" in html,
                "temporary clustered report rendered",
            )
        )

    with _temp_dir() as temp_dir:
        calibration_report = run_calibration(
            ROOT / "examples" / "calibration_targets.yaml",
            Path(temp_dir) / "calibration_out",
        )
        calibration_summary = pd.read_csv(
            Path(temp_dir) / "calibration_out" / "calibration_summary.csv"
        )
        checks.append(
            BenchmarkCheck(
                "calibration target checks pass",
                bool(
                    calibration_summary[calibration_summary["status"] == "calibrated"][
                        "passed"
                    ].all()
                ),
                "treatment and binary prevalence targets within tolerance",
            )
        )
        checks.append(
            BenchmarkCheck(
                "calibration writes report and calibrated DGP",
                calibration_report.exists()
                and (Path(temp_dir) / "calibration_out" / "calibrated_dgp.yaml").exists(),
                "calibration_report.html, calibrated_dgp.yaml",
            )
        )

    with _temp_dir() as temp_dir:
        temp_path = Path(temp_dir)
        grid_config = temp_path / "mini_grid.yaml"
        grid_config.write_text(
            "\n".join(
                [
                    "name: benchmark_mini_grid",
                    f"base_config: \"{(ROOT / 'examples' / 'causal_ate_observed_confounding.yaml').as_posix()}\"",
                    "sample_sizes: [120]",
                    "n_replications: 3",
                    "seed: 20260602",
                    "confounding_strengths: [0.0, 1.5]",
                    "heterogeneity_coefficients: [0.0, 0.5]",
                    "heterogeneity_modifier: X2",
                    "estimators:",
                    "  - naive_difference",
                    "  - aipw",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        grid_report = run_scenario_grid(grid_config, temp_path / "grid_out")
        scenario_summary = temp_path / "grid_out" / "scenario_summary.csv"
        grid_results = temp_path / "grid_out" / "grid_results.csv"
        checks.append(
            BenchmarkCheck(
                "scenario grid writes combined artifacts",
                grid_report.exists() and scenario_summary.exists() and grid_results.exists(),
                "report.html, scenario_summary.csv, grid_results.csv",
            )
        )

    with _temp_dir() as temp_dir:
        temp_path = Path(temp_dir)
        sensitivity_config = temp_path / "mini_sensitivity.yaml"
        sensitivity_config.write_text(
            "\n".join(
                [
                    "name: benchmark_mini_sensitivity",
                    f"base_config: \"{(ROOT / 'examples' / 'causal_binary_outcome.yaml').as_posix()}\"",
                    "sample_size: 600",
                    "n_replications: 8",
                    "seed: 20260602",
                    "U_to_treatment_strength: [0.0, 1.2]",
                    "U_to_outcome_strength: [0.0, 1.5]",
                    "estimators:",
                    "  - logistic_gcomp_risk_difference",
                    "  - aipw_risk_difference",
                    "  - adjusted_oracle_includes_U",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        sensitivity_report = run_sensitivity_grid(sensitivity_config, temp_path / "sensitivity_out")
        sensitivity_summary = pd.read_csv(temp_path / "sensitivity_out" / "sensitivity_summary.csv")
        low = sensitivity_summary[
            (sensitivity_summary["U_to_treatment_strength"] == 0.0)
            & (sensitivity_summary["U_to_outcome_strength"] == 0.0)
        ].iloc[0]
        high = sensitivity_summary[
            (sensitivity_summary["U_to_treatment_strength"] == 1.2)
            & (sensitivity_summary["U_to_outcome_strength"] == 1.5)
        ].iloc[0]
        checks.append(
            BenchmarkCheck(
                "zero-U sensitivity cell has small adjusted bias",
                abs(float(low["aipw_bias"])) < 0.12,
                f"aipw_bias={float(low['aipw_bias']):.3f}",
            )
        )
        checks.append(
            BenchmarkCheck(
                "strong latent U increases observed-estimator bias",
                abs(float(high["aipw_bias"])) > abs(float(low["aipw_bias"])) + 0.08,
                f"low={float(low['aipw_bias']):.3f}, high={float(high['aipw_bias']):.3f}",
            )
        )
        checks.append(
            BenchmarkCheck(
                "sensitivity grid writes combined artifacts",
                sensitivity_report.exists()
                and (temp_path / "sensitivity_out" / "sensitivity_summary.csv").exists()
                and (temp_path / "sensitivity_out" / "sensitivity_grid.csv").exists(),
                "report.html, sensitivity_summary.csv, sensitivity_grid.csv",
            )
        )

    return checks


def write_results(checks: list[BenchmarkCheck], path: str | Path) -> Path:
    results_path = Path(path)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# DGPForge Mini Benchmark Results",
        "",
        "These checks are small seeded smoke benchmarks for the Award C demo. They are intended to support the statistical story, not to provide exact numerical guarantees.",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        detail = check.detail.replace("|", "\\|")
        lines.append(f"| {check.name} | {status} | {detail} |")
    lines.extend(
        [
            "",
            "Interpretation:",
            "",
            "- Randomized treatment should make the naive estimator approximately unbiased.",
            "- Observed confounding should bias the naive estimator.",
            "- Adjusted OLS and AIPW should move closer to the known ATE in this simple linear DGP.",
            "- Heterogeneous-effect examples should report the analytical marginal ATE.",
            "- MCSE columns make finite Monte Carlo precision visible.",
            "- The double-robustness demo should show one-correct AIPW variants outperforming the double-misspecified variant in the seeded DGP.",
            "- Binary-outcome reports should expose marginal risks and risk-difference benchmarks.",
            "- Binary AIPW should recover the known marginal risk difference in the seeded demo.",
            "- Unmeasured-confounding sensitivity should show larger observed-estimator bias when latent U affects both treatment and outcome.",
            "- Count/rate outcomes should expose finite rate truth and offset-model benchmark checks.",
            "- Missing-data mechanisms should preserve full-data truth while masking observed outcomes.",
            "- Clustered data should report ICC diagnostics and cluster-aware SEs.",
            "- Calibration should write a calibrated DGP and target-vs-achieved summary.",
            "- Scenario-grid generation should produce combined CSV and HTML artifacts.",
            "- Sensitivity-grid generation should produce combined CSV and HTML artifacts.",
            "- Weak overlap should trigger a positivity warning.",
            "- Report generation should complete without relying on external datasets.",
        ]
    )
    results_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return results_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the DGPForge mini benchmark.")
    parser.add_argument("--write-results", action="store_true", help="Write benchmark/results.md.")
    parser.add_argument("--results-path", default=str(ROOT / "benchmark" / "results.md"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checks = run_checks()
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"{status}: {check.name} ({check.detail})")
    if args.write_results:
        path = write_results(checks, args.results_path)
        print(f"Wrote {path}")
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
