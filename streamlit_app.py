"""Optional DGPForge Streamlit demo."""

from __future__ import annotations

from pathlib import Path

import yaml
import pandas as pd

from dgpforge.agent import parse_paper_excerpt
from dgpforge.calibration import run_calibration
from dgpforge.contracts import load_contract
from dgpforge.grid import expand_grid, run_scenario_grid
from dgpforge.monte_carlo import run_monte_carlo
from dgpforge.report import generate_report
from dgpforge.sensitivity import expand_sensitivity_grid, run_sensitivity_grid


SCENARIOS = {
    "Randomized": {
        "kind": "config",
        "path": Path("examples/causal_ate_randomized.yaml"),
        "out": Path("examples/generated_reports/streamlit_demo/randomized"),
    },
    "Observed Confounding": {
        "kind": "config",
        "path": Path("examples/causal_ate_observed_confounding.yaml"),
        "out": Path("examples/generated_reports/streamlit_demo/observed_confounding"),
    },
    "Weak Overlap": {
        "kind": "config",
        "path": Path("examples/causal_ate_weak_overlap.yaml"),
        "out": Path("examples/generated_reports/streamlit_demo/weak_overlap"),
    },
    "Heterogeneous Effect": {
        "kind": "config",
        "path": Path("examples/causal_ate_heterogeneous_effect.yaml"),
        "out": Path("examples/generated_reports/streamlit_demo/heterogeneous_effect"),
    },
    "Double Robustness": {
        "kind": "config",
        "path": Path("examples/causal_ate_double_robustness.yaml"),
        "out": Path("examples/generated_reports/streamlit_demo/double_robustness"),
    },
    "Binary Outcome": {
        "kind": "config",
        "path": Path("examples/causal_binary_outcome.yaml"),
        "out": Path("examples/generated_reports/streamlit_demo/binary_outcome"),
    },
    "Count/Rate Outcome": {
        "kind": "config",
        "path": Path("examples/causal_count_rate_outcome.yaml"),
        "out": Path("examples/generated_reports/streamlit_demo/count_rate_outcome"),
    },
    "Missing Data": {
        "kind": "config",
        "path": Path("examples/missing_data_mechanisms.yaml"),
        "out": Path("examples/generated_reports/streamlit_demo/missing_data"),
    },
    "Clustered ICC": {
        "kind": "config",
        "path": Path("examples/clustered_ate_icc.yaml"),
        "out": Path("examples/generated_reports/streamlit_demo/clustered_icc"),
    },
    "DGP Calibration": {
        "kind": "calibration",
        "path": Path("examples/calibration_targets.yaml"),
        "out": Path("examples/generated_reports/streamlit_demo/calibration_demo"),
    },
    "Scenario Grid": {
        "kind": "grid",
        "path": Path("examples/scenario_grid_causal_ate.yaml"),
        "out": Path("examples/generated_reports/streamlit_demo/scenario_grid"),
    },
    "Unmeasured Confounding Sensitivity": {
        "kind": "sensitivity",
        "path": Path("examples/unmeasured_confounding_sensitivity.yaml"),
        "out": Path("examples/generated_reports/streamlit_demo/unmeasured_confounding_sensitivity"),
    },
    "From-Text Demo": {
        "kind": "text",
        "path": Path("examples/paper_excerpt_causal_ate.txt"),
        "out": Path("examples/generated_reports/streamlit_demo/from_text"),
    },
}


def _summary_csv_name(kind: str) -> str:
    if kind == "grid":
        return "scenario_summary.csv"
    if kind == "sensitivity":
        return "sensitivity_summary.csv"
    if kind == "calibration":
        return "calibration_summary.csv"
    return "estimator_summary.csv"


def _report_path(kind: str, out_dir: Path) -> Path:
    if kind == "calibration":
        return out_dir / "calibration_report.html"
    return out_dir / "report.html"


def _contract_summary(contract) -> dict[str, object]:
    return {
        "Scenario": contract.name,
        "Template": contract.template,
        "Sample sizes": contract.sample_sizes,
        "Replications": contract.n_replications,
        "Treatment assignment": contract.treatment.assignment,
        "Estimators": ", ".join(contract.estimators),
    }


def _show_plots(st, out_dir: Path) -> None:
    plot_paths = [
        out_dir / "bias_rmse.png",
        out_dir / "coverage.png",
        out_dir / "propensity_overlap.png",
        out_dir / "effect_heterogeneity.png",
        out_dir / "grid_bias.png",
        out_dir / "grid_coverage.png",
        out_dir / "sensitivity_bias_heatmap.png",
    ]
    existing = [path for path in plot_paths if path.exists()]
    if not existing:
        return
    st.subheader("Plots")
    for start in range(0, len(existing), 2):
        chunk = existing[start : start + 2]
        columns = st.columns(len(chunk))
        for column, path in zip(columns, chunk):
            column.image(str(path), caption=path.name, use_container_width=True)


def main() -> None:
    try:
        import streamlit as st
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Install the optional demo dependency with: python -m pip install -e '.[demo]'"
        ) from exc

    st.set_page_config(page_title="DGPForge", layout="wide")
    st.title("DGPForge")
    st.caption("Known-truth causal simulation studies for Monte Carlo estimator benchmarks.")
    st.info(
        "DGPForge benchmarks estimators against configured synthetic truth: marginal ATEs, risk estimands, count/rate estimands, missingness mechanisms, clustered ICC diagnostics, and calibrated design targets."
    )

    choice = st.sidebar.selectbox("Scenario", list(SCENARIOS))
    scenario = SCENARIOS[choice]
    out_dir = scenario["out"]

    assumptions_path = None
    calibration_config = None
    if scenario["kind"] == "config":
        contract = load_contract(scenario["path"])
        command = f"dgpforge run --config {scenario['path']} --out {out_dir}"
    elif scenario["kind"] == "grid":
        grid_config, contracts = expand_grid(scenario["path"])
        contract = contracts[0]
        command = f"dgpforge grid --config {scenario['path']} --out {out_dir}"
    elif scenario["kind"] == "sensitivity":
        sensitivity_config, contracts = expand_sensitivity_grid(scenario["path"])
        contract = contracts[0]
        command = f"dgpforge sensitivity --config {scenario['path']} --out {out_dir}"
    elif scenario["kind"] == "calibration":
        calibration_config = yaml.safe_load(scenario["path"].read_text(encoding="utf-8"))
        contract = None
        command = f"dgpforge calibrate --config {scenario['path']} --out {out_dir}"
    else:
        excerpt = scenario["path"].read_text(encoding="utf-8")
        st.subheader("Curated Paper Excerpt")
        st.text_area("Excerpt", excerpt, height=170, disabled=True, label_visibility="collapsed")
        contract, assumptions_path = parse_paper_excerpt(scenario["path"], out_dir)
        command = f"dgpforge from-text --input {scenario['path']} --out {out_dir}"

    left, right = st.columns([0.9, 1.1])
    with left:
        if scenario["kind"] in {"grid", "sensitivity"}:
            st.subheader("Grid Summary" if scenario["kind"] == "grid" else "Sensitivity Summary")
            config = grid_config if scenario["kind"] == "grid" else sensitivity_config
            st.json(
                {
                    "Name": config.get("name"),
                    "Cells": len(contracts),
                    "Sample sizes": config.get("sample_sizes") or config.get("sample_size"),
                    "Confounding strengths": config.get("confounding_strengths")
                    or config.get("U_to_treatment_strength"),
                    "Effect axis": config.get("heterogeneity_coefficients")
                    or config.get("U_to_outcome_strength"),
                    "Replications": config.get("n_replications"),
                },
                expanded=True,
            )
        elif scenario["kind"] == "calibration":
            calibration = calibration_config.get("calibration", {})
            st.subheader("Calibration Summary")
            st.json(
                {
                    "Name": calibration_config.get("name"),
                    "Base config": calibration_config.get("base_config"),
                    "Oracle n": calibration.get("oracle_n"),
                    "Seed": calibration.get("seed"),
                    "Targets": calibration.get("targets"),
                    "Tolerance": calibration.get("tolerance"),
                },
                expanded=True,
            )
        else:
            st.subheader("Contract Summary")
            st.json(_contract_summary(contract), expanded=True)
    with right:
        if scenario["kind"] in {"grid", "sensitivity"}:
            st.subheader("Grid Config" if scenario["kind"] == "grid" else "Sensitivity Config")
            config = grid_config if scenario["kind"] == "grid" else sensitivity_config
            st.code(yaml.safe_dump(config, sort_keys=False), language="yaml")
        elif scenario["kind"] == "calibration":
            st.subheader("Calibration Config")
            st.code(yaml.safe_dump(calibration_config, sort_keys=False), language="yaml")
        else:
            st.subheader("DGP Contract")
            st.code(
                yaml.safe_dump(contract.model_dump(mode="json"), sort_keys=False), language="yaml"
            )

    if st.button("Run benchmark and generate report", type="primary"):
        with st.spinner("Running deterministic Monte Carlo benchmark"):
            if scenario["kind"] == "grid":
                result = None
                report_path = run_scenario_grid(scenario["path"], out_dir)
            elif scenario["kind"] == "sensitivity":
                result = None
                report_path = run_sensitivity_grid(scenario["path"], out_dir)
            elif scenario["kind"] == "calibration":
                result = None
                report_path = run_calibration(scenario["path"], out_dir, command=command)
            else:
                result = run_monte_carlo(contract)
                report_path = generate_report(
                    contract,
                    result,
                    out_dir=out_dir,
                    command=command,
                    assumptions_log_path=assumptions_path,
                )

        st.success(f"Wrote {report_path}")
        if result is None:
            summary_name = _summary_csv_name(scenario["kind"])
            summary_title = {
                "grid": "Scenario Summary",
                "sensitivity": "Sensitivity Summary",
                "calibration": "Calibration Summary",
            }[scenario["kind"]]
            st.subheader(summary_title)
            st.dataframe(pd.read_csv(out_dir / summary_name), use_container_width=True)
        else:
            st.subheader("Estimator Summary")
            st.dataframe(result.summary, use_container_width=True)
        _show_plots(st, out_dir)
        if assumptions_path is not None and assumptions_path.exists():
            st.subheader("Assumptions Log")
            st.markdown(assumptions_path.read_text(encoding="utf-8"))
        st.markdown(f"Report path: `{report_path}`")

    elif _report_path(scenario["kind"], out_dir).exists():
        st.subheader("Existing Generated Report")
        st.markdown(f"Report path: `{_report_path(scenario['kind'], out_dir)}`")
        summary_path = out_dir / _summary_csv_name(scenario["kind"])
        if summary_path.exists():
            st.dataframe(pd.read_csv(summary_path), use_container_width=True)
        _show_plots(st, out_dir)


if __name__ == "__main__":
    main()
