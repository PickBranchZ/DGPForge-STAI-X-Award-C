"""Unmeasured-confounding sensitivity grids."""

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


def _estimator_label(name: object) -> str:
    return ESTIMATOR_LABELS.get(str(name), str(name).replace("_", " "))


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


def _scenario_contract(
    base_contract: DGPContract,
    *,
    sample_size: int,
    n_replications: int,
    seed: int,
    treatment_strength: float,
    outcome_strength: float,
    estimators: list[str] | None,
) -> DGPContract:
    data = base_contract.model_dump(mode="json")
    data["name"] = f"U_A{treatment_strength:g}_U_Y{outcome_strength:g}".replace(".", "p")
    data["sample_sizes"] = [int(sample_size)]
    data["n_replications"] = int(n_replications)
    data["seed"] = int(seed)
    config_name = data.get("unobserved_confounder", {}).get("name", "U")
    data["unobserved_confounder"] = {
        "enabled": True,
        "name": config_name,
        "distribution": "normal",
        "mean": 0.0,
        "sd": 1.0,
        "treatment_coefficient": float(treatment_strength),
        "outcome_coefficient": float(outcome_strength),
        "observed": False,
    }
    if estimators:
        data["estimators"] = estimators
    if config_name in data["covariates"]:
        raise ValueError("unobserved confounder name collides with an observed covariate")
    return DGPContract.model_validate(data)


def expand_sensitivity_grid(config_path: str | Path) -> tuple[dict[str, Any], list[DGPContract]]:
    """Expand a sensitivity-grid config into ordinary DGP contracts."""
    path, config = _load_config(config_path)
    base_contract = load_contract(_base_path(path, config))
    sample_size = int(config.get("sample_size", max(base_contract.sample_sizes)))
    n_replications = int(config.get("n_replications", base_contract.n_replications))
    seed = int(config.get("seed", base_contract.seed))
    treatment_strengths = config.get("U_to_treatment_strength", [0.0])
    outcome_strengths = config.get("U_to_outcome_strength", [0.0])
    estimators = config.get("estimators")

    contracts = []
    scenario_index = 0
    for treatment_strength in treatment_strengths:
        for outcome_strength in outcome_strengths:
            contracts.append(
                _scenario_contract(
                    base_contract,
                    sample_size=sample_size,
                    n_replications=n_replications,
                    seed=seed + scenario_index * 10_000,
                    treatment_strength=float(treatment_strength),
                    outcome_strength=float(outcome_strength),
                    estimators=estimators,
                )
            )
            scenario_index += 1
    return config, contracts


def _write_heatmap(grid: pd.DataFrame, out_dir: Path) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    selected_estimators = [
        estimator
        for estimator in [
            "naive_risk_difference",
            "logistic_gcomp_risk_difference",
            "ipw_risk_difference",
            "aipw_risk_difference",
            "adjusted_oracle_includes_U",
        ]
        if estimator in set(grid["estimator"])
    ]
    if not selected_estimators:
        selected_estimators = grid["estimator"].drop_duplicates().head(3).tolist()
    ncols = min(3, len(selected_estimators))
    nrows = int((len(selected_estimators) + ncols - 1) / ncols)
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(4.1 * ncols, 3.6 * nrows),
        constrained_layout=True,
    )
    if not isinstance(axes, (list, tuple)):
        axes_list = [axes]
    else:
        axes_list = list(axes)
    axes_list = list(getattr(axes, "flat", axes_list))
    finite_abs_bias = grid["bias"].abs()
    finite_abs_bias = finite_abs_bias[pd.notna(finite_abs_bias)]
    max_abs = max(float(finite_abs_bias.max()) if not finite_abs_bias.empty else 0.0, 0.05)
    image = None
    for axis, estimator in zip(axes_list, selected_estimators):
        subset = grid[grid["estimator"] == estimator]
        matrix = subset.pivot(
            index="U_to_outcome_strength",
            columns="U_to_treatment_strength",
            values="bias",
        ).sort_index(ascending=True)
        image = axis.imshow(
            matrix.to_numpy(),
            cmap="RdBu_r",
            vmin=-max_abs,
            vmax=max_abs,
            origin="lower",
            aspect="auto",
        )
        axis.set_title(_estimator_label(estimator), fontsize=10)
        axis.set_xlabel("U to treatment")
        axis.set_ylabel("U to outcome")
        axis.set_xticks(range(len(matrix.columns)))
        axis.set_xticklabels([f"{value:g}" for value in matrix.columns], fontsize=8)
        axis.set_yticks(range(len(matrix.index)))
        axis.set_yticklabels([f"{value:g}" for value in matrix.index], fontsize=8)
        for y_index, y_value in enumerate(matrix.index):
            for x_index, x_value in enumerate(matrix.columns):
                value = matrix.loc[y_value, x_value]
                axis.text(x_index, y_index, f"{value:.2f}", ha="center", va="center", fontsize=7)
    for axis in axes_list[len(selected_estimators) :]:
        axis.axis("off")
    if image is not None:
        fig.colorbar(image, ax=axes_list[: len(selected_estimators)], shrink=0.78, label="Bias")
    path = out_dir / "sensitivity_bias_heatmap.png"
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return path.name


def _write_report(
    *,
    config: dict[str, Any],
    out_dir: Path,
    summary: pd.DataFrame,
    grid: pd.DataFrame,
    heatmap_path: str,
    command: str,
) -> Path:
    table = summary.copy()
    display_columns = [
        "U_to_treatment_strength",
        "U_to_outcome_strength",
        "truth",
        "naive_bias",
        "gcomp_bias",
        "ipw_bias",
        "aipw_bias",
        "oracle_bias",
        "positivity_warning",
    ]
    display_columns = [column for column in display_columns if column in table.columns]
    display = table[display_columns].copy()
    for column in display.select_dtypes(include=["number"]).columns:
        display[column] = display[column].map(lambda value: f"{value:.3f}")
    display = display.rename(
        columns={
            "U_to_treatment_strength": "U to treatment",
            "U_to_outcome_strength": "U to outcome",
            "truth": "Known RD",
            "naive_bias": "Naive bias",
            "gcomp_bias": "G-comp bias",
            "ipw_bias": "IPW bias",
            "aipw_bias": "AIPW bias",
            "oracle_bias": "Oracle bias",
            "positivity_warning": "Positivity",
        }
    )
    table_html = display.to_html(index=False, escape=True, classes="data-table")

    detail = grid[
        [
            "U_to_treatment_strength",
            "U_to_outcome_strength",
            "estimator",
            "bias",
            "mcse_bias",
            "rmse",
            "coverage",
            "failure_rate",
        ]
    ].copy()
    detail["estimator"] = detail["estimator"].map(_estimator_label)
    for column in ["bias", "mcse_bias", "rmse", "coverage", "failure_rate"]:
        detail[column] = detail[column].map(lambda value: f"{value:.3f}")
    detail_html = detail.rename(
        columns={
            "U_to_treatment_strength": "U to treatment",
            "U_to_outcome_strength": "U to outcome",
            "estimator": "Estimator",
            "bias": "Bias",
            "mcse_bias": "MCSE bias",
            "rmse": "RMSE",
            "coverage": "Coverage",
            "failure_rate": "Failure rate",
        }
    ).to_html(index=False, escape=True, classes="data-table")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DGPForge Unmeasured-Confounding Sensitivity</title>
  <style>
    :root {{
      --ink: #172033;
      --muted: #5f6d82;
      --line: #d8deea;
      --panel: #f6f8fb;
      --accent: #2f6f7e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #fff;
      line-height: 1.5;
    }}
    header {{ border-bottom: 1px solid var(--line); background: #f7fafb; }}
    .hero, main {{ max-width: 1120px; margin: 0 auto; padding: 32px 24px; }}
    h1 {{ margin: 0; font-size: 34px; line-height: 1.1; letter-spacing: 0; }}
    h2 {{ margin: 28px 0 12px; font-size: 20px; letter-spacing: 0; }}
    .subtitle, .note {{ color: var(--muted); max-width: 850px; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(150px, 1fr)); gap: 12px; margin-top: 18px; }}
    .card {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 13px 14px; }}
    .label {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; font-weight: 800; }}
    .value {{ margin-top: 5px; font-size: 21px; font-weight: 800; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: #fff; }}
    table {{ width: 100%; min-width: 900px; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 8px 9px; text-align: right; white-space: nowrap; }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2), th:nth-child(3), td:nth-child(3) {{ text-align: left; }}
    th {{ background: var(--panel); color: #303a4d; font-size: 12px; }}
    figure {{ margin: 0; border: 1px solid var(--line); border-radius: 8px; padding: 10px; background: #fff; }}
    figure img {{ width: 100%; display: block; }}
    code {{ background: #eef3f7; border-radius: 5px; padding: 2px 5px; overflow-wrap: anywhere; }}
    @media (max-width: 850px) {{ .cards {{ grid-template-columns: 1fr; }} h1 {{ font-size: 29px; }} }}
  </style>
</head>
<body>
  <header>
    <div class="hero">
      <h1>Unmeasured-Confounding Sensitivity</h1>
      <p class="subtitle">This controlled synthetic grid varies a latent confounder <code>U</code> that is generated by the DGP but hidden from observed estimators. Known truth still comes from the configured potential outcomes.</p>
      <div class="cards">
        <div class="card"><div class="label">Grid cells</div><div class="value">{len(summary)}</div></div>
        <div class="card"><div class="label">Sample size</div><div class="value">{escape(str(config.get('sample_size')))}</div></div>
        <div class="card"><div class="label">Replications</div><div class="value">{escape(str(config.get('n_replications')))}</div></div>
        <div class="card"><div class="label">Outcome</div><div class="value">Binary</div></div>
      </div>
    </div>
  </header>
  <main>
    <h2>Bias Heatmap</h2>
    <p class="note">This is not a proof of robustness. It is a controlled simulation sensitivity study showing how unmeasured-confounding strength changes estimator bias under a known DGP.</p>
    <figure><img src="{escape(heatmap_path)}" alt="Bias heatmap by unmeasured-confounding strength"></figure>

    <h2>Grid Summary</h2>
    <p class="note">Bias is measured against the known marginal risk difference. MCSE of bias is available in the detailed estimator table.</p>
    <div class="table-wrap">{table_html}</div>

    <h2>Estimator Detail</h2>
    <div class="table-wrap">{detail_html}</div>

    <h2>Artifacts</h2>
    <p><a href="sensitivity_summary.csv">sensitivity_summary.csv</a> and <a href="sensitivity_grid.csv">sensitivity_grid.csv</a></p>
    <p><code>{escape(command)}</code></p>
  </main>
</body>
</html>
"""
    report_path = out_dir / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return report_path


def run_sensitivity_grid(
    config_path: str | Path,
    out_dir: str | Path,
    command: str | None = None,
) -> Path:
    """Run an unmeasured-confounding sensitivity grid."""
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config, contracts = expand_sensitivity_grid(config_path)

    grid_rows = []
    summary_rows = []
    for contract in contracts:
        result = run_monte_carlo(contract)
        scenario_dir = output_dir / contract.name
        save_contract(contract, scenario_dir / "contract.yaml")
        generate_report(
            contract,
            result,
            scenario_dir,
            command=f"dgpforge run --config {contract.name}/contract.yaml --out {contract.name}",
        )
        u = contract.unobserved_confounder
        summary = result.summary.copy()
        summary.insert(0, "scenario", contract.name)
        summary.insert(1, "U_to_treatment_strength", u.treatment_coefficient)
        summary.insert(2, "U_to_outcome_strength", u.outcome_coefficient)
        summary.insert(3, "truth", result.truth)
        grid_rows.append(summary)

        row = {
            "scenario": contract.name,
            "U_to_treatment_strength": u.treatment_coefficient,
            "U_to_outcome_strength": u.outcome_coefficient,
            "truth": result.truth,
            "positivity_warning": bool(result.diagnostics["positivity_warning"].any()),
        }
        bias_map = result.summary.set_index("estimator")["bias"].to_dict()
        row.update(
            {
                "naive_bias": float(bias_map.get("naive_risk_difference", float("nan"))),
                "gcomp_bias": float(bias_map.get("logistic_gcomp_risk_difference", float("nan"))),
                "ipw_bias": float(bias_map.get("ipw_risk_difference", float("nan"))),
                "aipw_bias": float(bias_map.get("aipw_risk_difference", float("nan"))),
                "oracle_bias": float(bias_map.get("adjusted_oracle_includes_U", float("nan"))),
            }
        )
        summary_rows.append(row)

    grid = pd.concat(grid_rows, ignore_index=True)
    summary = pd.DataFrame(summary_rows)
    grid.to_csv(output_dir / "sensitivity_grid.csv", index=False)
    summary.to_csv(output_dir / "sensitivity_summary.csv", index=False)
    heatmap_path = _write_heatmap(grid, output_dir)
    command = command or f"dgpforge sensitivity --config {config_path} --out {out_dir}"
    return _write_report(
        config=config,
        out_dir=output_dir,
        summary=summary,
        grid=grid,
        heatmap_path=heatmap_path,
        command=command,
    )
