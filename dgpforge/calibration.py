"""DGP calibration utilities."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import yaml

from dgpforge.contracts import load_contract, save_contract
from dgpforge.schema import DGPContract
from dgpforge.simulate import cluster_outcome_sd, simulate_dataset


def _load_config(config_path: str | Path) -> tuple[Path, dict[str, Any]]:
    path = Path(config_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return path, data


def _base_path(config_path: Path, config: dict[str, Any]) -> Path:
    base = Path(config["base_config"])
    if base.is_absolute():
        return base
    candidate = config_path.parent / base
    if candidate.exists():
        return candidate
    return Path.cwd() / base


def _contract_from_data(data: dict[str, Any]) -> DGPContract:
    return DGPContract.model_validate(data)


def _measure_treatment_prevalence(data: dict[str, Any], oracle_n: int, seed: int) -> float:
    contract = _contract_from_data(data)
    oracle = simulate_dataset(contract, n=oracle_n, seed=seed)
    return float(oracle["propensity"].mean())


def _measure_binary_control_prevalence(data: dict[str, Any], oracle_n: int, seed: int) -> float:
    contract = _contract_from_data(data)
    oracle = simulate_dataset(contract, n=oracle_n, seed=seed)
    return float(oracle["p0"].mean())


def _measure_count_baseline_rate(data: dict[str, Any], oracle_n: int, seed: int) -> float:
    contract = _contract_from_data(data)
    oracle = simulate_dataset(contract, n=oracle_n, seed=seed)
    exposure_spec = contract.outcome.exposure
    assert exposure_spec is not None
    exposure = oracle[exposure_spec.name]
    return float(oracle["mu0"].sum() / exposure.sum())


def _bisect_parameter(
    data: dict[str, Any],
    *,
    setter: Callable[[dict[str, Any], float], None],
    measure: Callable[[dict[str, Any]], float],
    target: float,
    low: float = -20.0,
    high: float = 20.0,
    max_iter: int = 70,
) -> tuple[float, float]:
    trial = yaml.safe_load(yaml.safe_dump(data))
    setter(trial, low)
    low_value = measure(trial)
    trial = yaml.safe_load(yaml.safe_dump(data))
    setter(trial, high)
    high_value = measure(trial)
    if not (low_value <= target <= high_value):
        raise ValueError(
            f"target {target:g} outside calibration range [{low_value:g}, {high_value:g}]"
        )
    best = high
    achieved = high_value
    for _ in range(max_iter):
        mid = (low + high) / 2.0
        trial = yaml.safe_load(yaml.safe_dump(data))
        setter(trial, mid)
        value = measure(trial)
        best = mid
        achieved = value
        if value < target:
            low = mid
        else:
            high = mid
    setter(data, best)
    return float(best), float(achieved)


def _tolerance(tolerances: dict[str, Any], *names: str, default: float) -> float:
    for name in names:
        if name in tolerances:
            return float(tolerances[name])
    return default


def calibrate_contract(config_path: str | Path) -> tuple[DGPContract, pd.DataFrame, dict[str, Any]]:
    """Calibrate a base DGP contract according to a calibration config."""
    path, config = _load_config(config_path)
    base_contract = load_contract(_base_path(path, config))
    calibration = config.get("calibration", config)
    oracle_n = int(calibration.get("oracle_n", 50_000))
    seed = int(calibration.get("seed", base_contract.seed + 404_001))
    targets = calibration.get("targets", {})
    tolerances = calibration.get("tolerance", {})
    data = base_contract.model_dump(mode="json")
    rows: list[dict[str, Any]] = []

    def add_row(
        target_name: str,
        target_value: float,
        achieved_value: float,
        tolerance: float,
        parameter: str,
        calibrated_value: float,
        status: str = "calibrated",
    ) -> None:
        abs_error = abs(float(achieved_value) - float(target_value))
        rows.append(
            {
                "target": target_name,
                "target_value": float(target_value),
                "achieved_value": float(achieved_value),
                "absolute_error": abs_error,
                "tolerance": float(tolerance),
                "passed": bool(abs_error <= tolerance) if status == "calibrated" else False,
                "parameter": parameter,
                "calibrated_value": float(calibrated_value),
                "status": status,
            }
        )

    if "treatment_prevalence" in targets:
        target = float(targets["treatment_prevalence"])
        tolerance = _tolerance(tolerances, "treatment_prevalence", default=0.01)

        def setter(trial: dict[str, Any], value: float) -> None:
            trial["treatment"]["formula"]["intercept"] = float(value)

        value, achieved = _bisect_parameter(
            data,
            setter=setter,
            measure=lambda trial: _measure_treatment_prevalence(trial, oracle_n, seed),
            target=target,
        )
        add_row(
            "treatment_prevalence",
            target,
            achieved,
            tolerance,
            "treatment.formula.intercept",
            value,
        )

    if "binary_outcome_prevalence_control" in targets:
        target = float(targets["binary_outcome_prevalence_control"])
        tolerance = _tolerance(
            tolerances, "binary_outcome_prevalence_control", "outcome_prevalence", default=0.01
        )
        if data["outcome"]["type"] != "binary":
            add_row(
                "binary_outcome_prevalence_control",
                target,
                float("nan"),
                tolerance,
                "outcome.coefficients.intercept",
                float("nan"),
                "skipped",
            )
        else:

            def setter(trial: dict[str, Any], value: float) -> None:
                trial["outcome"]["coefficients"]["intercept"] = float(value)

            value, achieved = _bisect_parameter(
                data,
                setter=setter,
                measure=lambda trial: _measure_binary_control_prevalence(trial, oracle_n, seed),
                target=target,
            )
            add_row(
                "binary_outcome_prevalence_control",
                target,
                achieved,
                tolerance,
                "outcome.coefficients.intercept",
                value,
            )

    if "count_baseline_rate" in targets:
        target = float(targets["count_baseline_rate"])
        tolerance = _tolerance(
            tolerances, "count_baseline_rate", "count_rate", default=max(target * 0.05, 1e-6)
        )
        if data["outcome"]["type"] != "count":
            add_row(
                "count_baseline_rate",
                target,
                float("nan"),
                tolerance,
                "outcome.coefficients.intercept",
                float("nan"),
                "skipped",
            )
        else:

            def setter(trial: dict[str, Any], value: float) -> None:
                trial["outcome"]["coefficients"]["intercept"] = float(value)

            value, achieved = _bisect_parameter(
                data,
                setter=setter,
                measure=lambda trial: _measure_count_baseline_rate(trial, oracle_n, seed),
                target=target,
            )
            add_row(
                "count_baseline_rate",
                target,
                achieved,
                tolerance,
                "outcome.coefficients.intercept",
                value,
            )

    if "icc" in targets:
        target = float(targets["icc"])
        tolerance = _tolerance(tolerances, "icc", default=0.01)
        if not data.get("clusters", {}).get("enabled") or data["outcome"]["type"] != "continuous":
            add_row("icc", target, float("nan"), tolerance, "clusters.icc", float("nan"), "skipped")
        else:
            data["clusters"]["icc"] = target
            calibrated = _contract_from_data(data)
            sd = cluster_outcome_sd(calibrated)
            data["clusters"]["random_intercept"]["outcome_sd"] = sd
            add_row("icc", target, target, tolerance, "clusters.icc", target)

    calibrated_contract = _contract_from_data(data)
    summary = pd.DataFrame(rows)
    meta = {"oracle_n": oracle_n, "seed": seed, "config": config}
    return calibrated_contract, summary, meta


def _write_report(
    out_dir: Path,
    summary: pd.DataFrame,
    calibrated_path: Path,
    command: str,
    meta: dict[str, Any],
) -> Path:
    display = summary.copy()
    for column in [
        "target_value",
        "achieved_value",
        "absolute_error",
        "tolerance",
        "calibrated_value",
    ]:
        display[column] = display[column].map(
            lambda value: "NA" if not pd.notna(value) else f"{float(value):.6g}"
        )
    table_html = display.rename(
        columns={
            "target": "Target",
            "target_value": "Target value",
            "achieved_value": "Achieved value",
            "absolute_error": "Abs. error",
            "tolerance": "Tolerance",
            "passed": "Pass",
            "parameter": "Parameter",
            "calibrated_value": "Calibrated value",
            "status": "Status",
        }
    ).to_html(index=False, escape=True, classes="data-table")
    all_passed = (
        bool(summary[summary["status"] == "calibrated"]["passed"].all())
        if not summary.empty
        else False
    )
    badge = "Pass" if all_passed else "Review"
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DGPForge Calibration Report</title>
  <style>
    * {{ box-sizing: border-box; }}
    html {{ max-width: 100%; overflow-x: hidden; }}
    body {{ margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #172033; line-height: 1.5; max-width: 100%; overflow-x: hidden; }}
    header {{ background: #f7fafb; border-bottom: 1px solid #d8deea; }}
    .hero, main {{ width: 100%; max-width: 1080px; margin: 0 auto; padding: 32px 24px; }}
    h1 {{ margin: 0; font-size: 34px; letter-spacing: 0; }}
    h2 {{ margin: 26px 0 12px; font-size: 20px; letter-spacing: 0; }}
    .subtitle, .note {{ color: #5f6d82; max-width: 860px; }}
    p, h1, h2, td, th, code {{ overflow-wrap: anywhere; }}
    .cards {{ display: grid; grid-template-columns: repeat(3, minmax(170px, 1fr)); gap: 12px; margin-top: 18px; }}
    .card {{ border: 1px solid #d8deea; border-radius: 8px; background: #f6f8fb; padding: 14px; }}
    .label {{ color: #5f6d82; font-size: 11px; text-transform: uppercase; letter-spacing: .08em; font-weight: 800; }}
    .value {{ margin-top: 6px; font-size: 22px; font-weight: 800; overflow-wrap: anywhere; }}
    .table-wrap {{ max-width: 100%; overflow-x: auto; border: 1px solid #d8deea; border-radius: 8px; }}
    table {{ width: 100%; min-width: 860px; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #d8deea; padding: 8px 9px; text-align: right; white-space: nowrap; }}
    th:first-child, td:first-child, th:nth-child(7), td:nth-child(7), th:nth-child(9), td:nth-child(9) {{ text-align: left; }}
    th {{ background: #f6f8fb; color: #303a4d; font-size: 12px; }}
    code {{ background: #eef3f7; border-radius: 5px; padding: 2px 5px; white-space: normal; }}
    @media (max-width: 850px) {{
      .hero, main {{ padding-left: 16px; padding-right: 16px; }}
      .cards {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 29px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="hero">
      <h1>DGP Calibration Engine</h1>
      <p class="subtitle">Calibration turns requested synthetic DGP targets into DGP parameters, then checks achieved values under the configured covariate distribution. These are simulation-design quantities, not real-data parameters and not calibration to official STAI-X or external real data.</p>
      <div class="cards">
        <div class="card"><div class="label">Status</div><div class="value">{escape(badge)}</div></div>
        <div class="card"><div class="label">Oracle n</div><div class="value">{int(meta['oracle_n'])}</div></div>
        <div class="card"><div class="label">Seed</div><div class="value">{int(meta['seed'])}</div></div>
      </div>
    </div>
  </header>
  <main>
    <h2>Target vs Achieved</h2>
    <div class="table-wrap">{table_html}</div>
    <p class="note">Calibration is approximate and depends on the specified covariate distribution, oracle sample size, and compatible target/contract pairs. Skipped rows indicate targets that do not apply to the selected base DGP; failed rows are reported rather than silently accepted.</p>

    <h2>Outputs</h2>
    <p><code>{escape(str(calibrated_path.name))}</code> contains the calibrated DGP contract.</p>
    <p><code>calibration_summary.csv</code> contains the table above.</p>

    <h2>Reproducibility</h2>
    <p><code>{escape(command)}</code></p>
  </main>
</body>
</html>
"""
    report_path = out_dir / "calibration_report.html"
    report_path.write_text(html, encoding="utf-8")
    return report_path


def run_calibration(
    config_path: str | Path, out_dir: str | Path, command: str | None = None
) -> Path:
    """Run calibration and write calibrated_dgp.yaml plus report artifacts."""
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    calibrated_contract, summary, meta = calibrate_contract(config_path)
    calibrated_path = save_contract(calibrated_contract, output_dir / "calibrated_dgp.yaml")
    summary.to_csv(output_dir / "calibration_summary.csv", index=False)
    command_text = command or f"dgpforge calibrate --config {config_path} --out {out_dir}"
    return _write_report(output_dir, summary, calibrated_path, command_text, meta)
