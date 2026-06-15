"""Scenario-grid expansion for DGPForge contracts."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from dgpforge.contracts import load_contract, save_contract
from dgpforge.monte_carlo import run_monte_carlo
from dgpforge.report import ESTIMATOR_LABELS, generate_report
from dgpforge.schema import DGPContract


def _rel(path: Path, start: Path) -> str:
    return path.relative_to(start).as_posix()


def _format_number(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _estimator_label(name: object) -> str:
    return ESTIMATOR_LABELS.get(str(name), str(name).replace("_", " "))


def _confounding_label(strength: float) -> str:
    if strength == 0:
        return "randomized"
    if strength <= 1.0:
        return "moderate_confounding"
    return "strong_confounding"


def _effect_label(coefficient: float) -> str:
    return "heterogeneous_effect" if coefficient != 0 else "constant_effect"


def _scenario_title(strength: float, coefficient: float, sample_size: int) -> str:
    confounding = _confounding_label(strength).replace("_", " ")
    effect = _effect_label(coefficient).replace("_", " ")
    return f"{confounding}, {effect}, n={sample_size}".title()


def _load_grid_config(config_path: str | Path) -> tuple[Path, dict[str, Any]]:
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


def _scaled_treatment(base_contract: DGPContract, strength: float) -> dict[str, Any]:
    base_formula = base_contract.treatment.formula
    if strength == 0:
        return {
            "name": base_contract.treatment.name,
            "type": base_contract.treatment.type,
            "assignment": "randomized",
            "formula": {"intercept": 0.0},
        }

    treatment_terms = {
        name: coefficient for name, coefficient in base_formula.items() if name != "intercept"
    }
    max_abs = max((abs(value) for value in treatment_terms.values()), default=1.0)
    scale = strength / max_abs if max_abs else 1.0
    formula = {"intercept": base_formula.get("intercept", -0.2)}
    formula.update({name: coefficient * scale for name, coefficient in treatment_terms.items()})
    return {
        "name": base_contract.treatment.name,
        "type": base_contract.treatment.type,
        "assignment": "logistic",
        "formula": formula,
    }


def _scenario_contract(
    base_contract: DGPContract,
    *,
    sample_size: int,
    n_replications: int,
    seed: int,
    strength: float,
    heterogeneity_coefficient: float,
    heterogeneity_modifier: str | None,
    estimators: list[str] | None,
) -> DGPContract:
    data = base_contract.model_dump(mode="json")
    key = (
        f"{_confounding_label(strength)}_"
        f"{_effect_label(heterogeneity_coefficient)}_n{sample_size}"
    )
    data["name"] = key
    data["sample_sizes"] = [int(sample_size)]
    data["n_replications"] = int(n_replications)
    data["seed"] = int(seed)
    data["treatment"] = _scaled_treatment(base_contract, strength)
    modifier = (
        heterogeneity_modifier
        or base_contract.outcome.treatment_effect_heterogeneity.modifier
        or next(iter(base_contract.covariates))
    )
    data["outcome"]["treatment_effect_heterogeneity"] = {
        "enabled": bool(heterogeneity_coefficient != 0),
        "modifier": modifier,
        "coefficient": float(heterogeneity_coefficient),
    }
    if estimators:
        data["estimators"] = estimators
    return DGPContract.model_validate(data)


def expand_grid(config_path: str | Path) -> tuple[dict[str, Any], list[DGPContract]]:
    """Expand a grid YAML file into ordinary DGP contracts."""
    path, config = _load_grid_config(config_path)
    base_contract = load_contract(_base_path(path, config))
    sample_sizes = config.get("sample_sizes", base_contract.sample_sizes)
    strengths = config.get("confounding_strengths", [0.0])
    heterogeneity_coefficients = config.get("heterogeneity_coefficients", [0.0])
    n_replications = int(config.get("n_replications", base_contract.n_replications))
    seed = int(config.get("seed", base_contract.seed))
    heterogeneity_modifier = config.get("heterogeneity_modifier")
    estimators = config.get("estimators")

    contracts = []
    scenario_index = 0
    for sample_size in sample_sizes:
        for strength in strengths:
            for heterogeneity_coefficient in heterogeneity_coefficients:
                contracts.append(
                    _scenario_contract(
                        base_contract,
                        sample_size=int(sample_size),
                        n_replications=n_replications,
                        seed=seed + scenario_index * 10_000,
                        strength=float(strength),
                        heterogeneity_coefficient=float(heterogeneity_coefficient),
                        heterogeneity_modifier=heterogeneity_modifier,
                        estimators=estimators,
                    )
                )
                scenario_index += 1
    return config, contracts


def _write_grid_plots(results: pd.DataFrame, out_dir: Path) -> dict[str, str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    paths: dict[str, str] = {}
    selected = results[
        results["estimator"].isin(["naive_difference", "adjusted_ols", "ipw", "aipw"])
    ]
    if selected.empty:
        selected = results
    selected = selected.copy()
    selected["display_scenario"] = (
        selected["sample_size"].astype(str)
        + " | c="
        + selected["confounding_strength"].map(lambda value: f"{value:.1f}")
        + " | h="
        + selected["heterogeneity_coefficient"].map(lambda value: f"{value:.2f}")
    )

    scenarios = selected["display_scenario"].drop_duplicates().tolist()
    y_positions = range(len(scenarios))
    fig, ax = plt.subplots(figsize=(10, max(4.0, len(scenarios) * 0.34)), constrained_layout=True)
    offsets = {
        "naive_difference": -0.24,
        "adjusted_ols": -0.08,
        "ipw": 0.08,
        "aipw": 0.24,
    }
    colors = {
        "naive_difference": "#b35c37",
        "adjusted_ols": "#2f6f7e",
        "ipw": "#6a5d9b",
        "aipw": "#27794f",
    }
    labels = {
        "naive_difference": "Naive",
        "adjusted_ols": "Adjusted OLS",
        "ipw": "IPW",
        "aipw": "AIPW",
    }
    for estimator, group in selected.groupby("estimator", sort=False):
        if estimator not in offsets:
            continue
        lookup = group.set_index("display_scenario")["bias"].abs()
        ax.scatter(
            [lookup.get(scenario, float("nan")) for scenario in scenarios],
            [position + offsets[estimator] for position in y_positions],
            label=labels.get(estimator, estimator),
            color=colors.get(estimator, "#34495e"),
            s=30,
        )
    ax.set_yticks(list(y_positions))
    ax.set_yticklabels(scenarios, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Absolute bias against known ATE")
    ax.set_title("Scenario-grid bias scan")
    ax.grid(alpha=0.25, axis="x")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, frameon=False)
    bias_path = out_dir / "grid_bias.png"
    fig.savefig(bias_path, dpi=170)
    plt.close(fig)
    paths["grid_bias"] = bias_path.name

    fig, ax = plt.subplots(figsize=(9, 4.5), constrained_layout=True)
    aipw_rows = (
        results[results["estimator"] == "aipw"]
        .groupby(["confounding_strength", "heterogeneity_coefficient"], as_index=False)["coverage"]
        .mean()
    )
    for coefficient, group in aipw_rows.groupby("heterogeneity_coefficient", sort=False):
        label = "constant effect" if coefficient == 0 else f"heterogeneity={coefficient:g}"
        ax.plot(
            group["confounding_strength"],
            group["coverage"],
            marker="o",
            linewidth=2,
            label=label,
        )
    ax.axhline(0.95, color="#2f3747", linestyle="--", linewidth=1, label="Nominal 95%")
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Confounding strength")
    ax.set_ylabel("AIPW coverage")
    ax.set_title("Coverage scan for the main AIPW estimator")
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, frameon=False)
    coverage_path = out_dir / "grid_coverage.png"
    fig.savefig(coverage_path, dpi=170)
    plt.close(fig)
    paths["grid_coverage"] = coverage_path.name
    return paths


def _write_grid_report(
    *,
    config: dict[str, Any],
    out_dir: Path,
    scenario_summary: pd.DataFrame,
    grid_results: pd.DataFrame,
    plot_paths: dict[str, str],
    command: str,
) -> Path:
    rows = []
    for _, row in scenario_summary.iterrows():
        positivity = "Warning" if row["positivity_warning"] else "Pass"
        rows.append(
            f"""
            <tr>
              <td>{escape(str(row['scenario_title']))}</td>
              <td>{int(row['sample_size'])}</td>
              <td>{float(row['confounding_strength']):.2f}</td>
              <td>{float(row['heterogeneity_coefficient']):.2f}</td>
              <td>{float(row['truth']):.3f}</td>
              <td>{float(row['treatment_prevalence']):.3f}</td>
              <td>{float(row['propensity_overlap_width']):.3f}</td>
              <td>{escape(positivity)}</td>
              <td>{escape(_estimator_label(row['best_estimator']))}</td>
              <td><a href="{escape(str(row['report_href']))}">report.html</a></td>
            </tr>
            """
        )

    estimator_rows = grid_results[
        [
            "scenario_title",
            "estimator",
            "sample_size",
            "bias",
            "mcse_bias",
            "rmse",
            "coverage",
            "mcse_coverage",
            "failure_rate",
        ]
    ].copy()
    estimator_rows["estimator"] = estimator_rows["estimator"].map(_estimator_label)
    for column in [
        "bias",
        "mcse_bias",
        "rmse",
        "coverage",
        "mcse_coverage",
        "failure_rate",
    ]:
        estimator_rows[column] = estimator_rows[column].map(_format_number)
    estimator_html = estimator_rows.rename(
        columns={
            "scenario_title": "Scenario",
            "estimator": "Estimator",
            "sample_size": "n",
            "bias": "Bias",
            "mcse_bias": "MCSE bias",
            "rmse": "RMSE",
            "coverage": "Coverage",
            "mcse_coverage": "MCSE coverage",
            "failure_rate": "Failure rate",
        }
    ).to_html(index=False, escape=True, classes="data-table")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DGPForge Scenario Grid</title>
  <style>
    :root {{
      --ink: #172033;
      --muted: #5f6d82;
      --line: #d8deea;
      --panel: #f6f8fb;
      --accent: #2f6f7e;
      --warn-bg: #fff2e8;
      --warn: #954817;
      --ok-bg: #eaf6ef;
      --ok: #256d49;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #ffffff;
      line-height: 1.5;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      background: #f7fafb;
    }}
    .hero, main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 24px;
    }}
    h1 {{
      margin: 0;
      font-size: 34px;
      line-height: 1.1;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 28px 0 12px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    .subtitle, .note {{
      color: var(--muted);
      max-width: 820px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 12px;
      margin-top: 18px;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 13px 14px;
    }}
    .label {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .08em;
      font-weight: 800;
    }}
    .value {{
      margin-top: 5px;
      font-size: 21px;
      font-weight: 800;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }}
    table {{
      width: 100%;
      min-width: 980px;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 9px;
      text-align: left;
      white-space: nowrap;
    }}
    th {{
      background: var(--panel);
      color: #303a4d;
      font-size: 12px;
    }}
    .plot-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(300px, 1fr));
      gap: 16px;
    }}
    figure {{
      margin: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fff;
    }}
    figure img {{
      width: 100%;
      display: block;
    }}
    code {{
      background: #eef3f7;
      border-radius: 5px;
      padding: 2px 5px;
    }}
    @media (max-width: 850px) {{
      .cards,
      .plot-grid {{
        grid-template-columns: 1fr;
      }}
      h1 {{
        font-size: 29px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="hero">
      <h1>DGPForge Scenario Grid</h1>
      <p class="subtitle">This illustrative grid expands one base DGP into seeded scenarios across sample size, confounding strength, and treatment-effect heterogeneity. Known truth is the truth of each configured synthetic DGP, not real-world truth.</p>
      <div class="cards">
        <div class="card"><div class="label">Scenarios</div><div class="value">{len(scenario_summary)}</div></div>
        <div class="card"><div class="label">Sample sizes</div><div class="value">{escape(', '.join(map(str, config.get('sample_sizes', []))))}</div></div>
        <div class="card"><div class="label">Confounding strengths</div><div class="value">{escape(', '.join(map(str, config.get('confounding_strengths', []))))}</div></div>
        <div class="card"><div class="label">Replications</div><div class="value">{escape(str(config.get('n_replications')))}</div></div>
      </div>
    </div>
  </header>
  <main>
    <h2>Scenario Summary</h2>
    <p class="note">Positivity pass/warning refers only to overlap diagnostics. Estimator rankings are finite Monte Carlo evidence under these seeded examples.</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Scenario</th><th>n</th><th>Confounding</th><th>HTE coeff</th><th>True ATE</th><th>Treat prev.</th><th>Overlap width</th><th>Positivity</th><th>Best RMSE</th><th>Report</th></tr>
        </thead>
        <tbody>
          {"".join(rows)}
        </tbody>
      </table>
    </div>

    <h2>Grid Plots</h2>
    <div class="plot-grid">
      <figure><img src="{escape(plot_paths['grid_bias'])}" alt="Scenario grid bias scan"></figure>
      <figure><img src="{escape(plot_paths['grid_coverage'])}" alt="Scenario grid coverage scan"></figure>
    </div>

    <h2>Estimator Results</h2>
    <p class="note">MCSE columns quantify simulation uncertainty from finite replications; estimator standard errors quantify uncertainty within a fitted replication.</p>
    <div class="table-wrap">{estimator_html}</div>

    <h2>Artifacts</h2>
    <p><a href="grid_results.csv">grid_results.csv</a> and <a href="scenario_summary.csv">scenario_summary.csv</a></p>
    <p><code>{escape(command)}</code></p>
  </main>
</body>
</html>
"""
    report_path = out_dir / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return report_path


def run_scenario_grid(
    config_path: str | Path,
    out_dir: str | Path,
    command: str | None = None,
) -> Path:
    """Run a scenario grid and write a combined report."""
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config, contracts = expand_grid(config_path)

    result_rows = []
    scenario_rows = []
    for contract in contracts:
        result = run_monte_carlo(contract)
        scenario_dir = output_dir / contract.name
        scenario_command = (
            f"dgpforge run --config {contract.name}/contract.yaml --out {contract.name}"
        )
        save_contract(contract, scenario_dir / "contract.yaml")
        generate_report(contract, result, scenario_dir, command=scenario_command)
        strength = max(
            (abs(value) for key, value in contract.treatment.formula.items() if key != "intercept"),
            default=0.0,
        )
        heterogeneity = contract.outcome.treatment_effect_heterogeneity
        original_summary = result.summary.copy()
        original_summary.insert(0, "scenario", contract.name)
        original_summary.insert(
            1,
            "scenario_title",
            _scenario_title(strength, heterogeneity.coefficient, contract.sample_sizes[0]),
        )
        original_summary.insert(2, "confounding_strength", float(strength))
        original_summary.insert(3, "heterogeneity_coefficient", float(heterogeneity.coefficient))
        original_summary.insert(4, "truth", float(result.truth))
        result_rows.append(original_summary)

        best = result.summary.sort_values("rmse").iloc[0]
        diagnostics = result.diagnostics.iloc[0]
        scenario_rows.append(
            {
                "scenario": contract.name,
                "scenario_title": _scenario_title(
                    strength, heterogeneity.coefficient, contract.sample_sizes[0]
                ),
                "sample_size": contract.sample_sizes[0],
                "confounding_strength": float(strength),
                "heterogeneity_coefficient": float(heterogeneity.coefficient),
                "truth": float(result.truth),
                "treatment_prevalence": float(diagnostics["treatment_prevalence"]),
                "propensity_overlap_width": float(diagnostics["propensity_overlap_width"]),
                "positivity_warning": bool(diagnostics["positivity_warning"]),
                "best_estimator": str(best["estimator"]),
                "best_rmse": float(best["rmse"]),
                "report_href": f"{contract.name}/report.html",
            }
        )

    grid_results = pd.concat(result_rows, ignore_index=True)
    scenario_summary = pd.DataFrame(scenario_rows)
    grid_results.to_csv(output_dir / "grid_results.csv", index=False)
    scenario_summary.to_csv(output_dir / "scenario_summary.csv", index=False)
    plot_paths = _write_grid_plots(grid_results, output_dir)
    command = command or f"dgpforge grid --config {config_path} --out {out_dir}"
    return _write_grid_report(
        config=config,
        out_dir=output_dir,
        scenario_summary=scenario_summary,
        grid_results=grid_results,
        plot_paths=plot_paths,
        command=command,
    )
