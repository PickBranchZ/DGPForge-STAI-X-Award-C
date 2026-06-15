"""HTML report generation."""

from __future__ import annotations

from html import escape
from numbers import Number
from pathlib import Path
from typing import SupportsFloat, cast

import pandas as pd

from dgpforge.contracts import save_contract
from dgpforge.reporting.labels import (
    estimator_label as _estimator_label,
    template_label as _template_label,
    title_case_name as _title_case_name,
)
from dgpforge.schema import DGPContract
from dgpforge.simulate import simulate_dataset


def _format_number(value: object) -> str:
    if isinstance(value, Number) and not isinstance(value, bool):
        if not pd.notna(value):
            return "NA"
        return f"{float(cast(SupportsFloat, value)):.3f}"
    return str(value)


def _html_table(frame: pd.DataFrame, columns: list[str]) -> str:
    labels = {
        "sample_size": "n",
        "estimator": "Estimator",
        "mean_estimate": "Mean estimate",
        "bias": "Bias",
        "mcse_bias": "MCSE bias",
        "rmse": "RMSE",
        "mcse_rmse": "MCSE RMSE",
        "empirical_sd": "Empirical SD",
        "mean_estimated_se": "Mean SE",
        "coverage": "95% coverage",
        "mcse_coverage": "MCSE coverage",
        "n_replications": "Replications",
        "n_attempted": "Attempted",
        "n_valid": "Valid",
        "n_coverage": "Coverage n",
        "n_failed": "Failed",
        "n_not_applicable": "Not applicable",
        "n_non_ok": "Non-ok",
        "failure_rate": "Failure rate",
        "non_ok_rate": "Non-ok rate",
        "failure_rate_denominator": "Failure denominator",
        "first_error_type": "First error type",
        "first_error_message": "First error message",
        "status_message": "Status",
    }
    display = frame[columns].copy()
    if "estimator" in display.columns:
        display["estimator"] = display["estimator"].map(_estimator_label)
    for column in display.columns:
        display[column] = display[column].map(_format_number)
    display = display.rename(columns=labels)
    return display.to_html(index=False, escape=True, classes="data-table")


def _write_plots(
    contract: DGPContract,
    summary: pd.DataFrame,
    out_dir: Path,
) -> dict[str, str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    paths: dict[str, str] = {}
    colors = {
        "naive_difference": "#b35c37",
        "adjusted_ols": "#2f6f7e",
        "adjusted_ols_omit_confounder": "#6f7e86",
        "ipw": "#6a5d9b",
        "ipw_omit_confounder": "#8b6d42",
        "aipw": "#27794f",
        "aipw_ps_misspecified": "#4b8bb8",
        "aipw_outcome_misspecified": "#9a6aa8",
        "aipw_double_misspecified": "#9b3f42",
        "naive_risk_difference": "#b35c37",
        "logistic_gcomp_risk_difference": "#2f6f7e",
        "ipw_risk_difference": "#6a5d9b",
        "aipw_risk_difference": "#27794f",
        "adjusted_oracle_includes_U": "#455a64",
        "naive_rate_difference": "#b35c37",
        "poisson_offset_gcomp_rate_difference": "#2f6f7e",
        "ipw_rate_difference": "#6a5d9b",
        "naive_difference_complete_case": "#b35c37",
        "adjusted_ols_complete_case": "#2f6f7e",
        "aipw_complete_case": "#27794f",
        "adjusted_ols_missingness_ipw": "#6a5d9b",
        "logistic_gcomp_complete_case": "#2f6f7e",
        "rate_gcomp_complete_case": "#2f6f7e",
        "adjusted_ols_naive_se": "#b35c37",
        "adjusted_ols_cluster_robust": "#2f6f7e",
    }
    labels = {
        "naive_difference": "Naive diff.",
        "adjusted_ols": "Adjusted OLS",
        "adjusted_ols_omit_confounder": "OLS confounders omitted",
        "ipw": "IPW",
        "ipw_omit_confounder": "IPW confounders omitted",
        "aipw": "AIPW",
        "aipw_ps_misspecified": "AIPW PS wrong",
        "aipw_outcome_misspecified": "AIPW outcome wrong",
        "aipw_double_misspecified": "AIPW both wrong",
        "naive_risk_difference": "Naive RD",
        "logistic_gcomp_risk_difference": "Logistic g-comp RD",
        "ipw_risk_difference": "IPW RD",
        "aipw_risk_difference": "AIPW RD",
        "adjusted_oracle_includes_U": "Oracle incl. U",
        "naive_rate_difference": "Naive rate diff.",
        "poisson_offset_gcomp_rate_difference": "Poisson offset g-comp",
        "ipw_rate_difference": "IPW rate diff.",
        "naive_difference_complete_case": "Naive CC",
        "adjusted_ols_complete_case": "Adjusted OLS CC",
        "aipw_complete_case": "AIPW CC",
        "adjusted_ols_missingness_ipw": "Missingness-IPW OLS",
        "logistic_gcomp_complete_case": "Logistic g-comp CC",
        "rate_gcomp_complete_case": "Rate g-comp CC",
        "adjusted_ols_naive_se": "OLS naive SE",
        "adjusted_ols_cluster_robust": "OLS cluster-robust",
    }
    if contract.outcome.type == "binary":
        target_label = "known marginal risk difference"
    elif contract.outcome.type == "count":
        target_label = "known marginal rate difference"
    else:
        target_label = "known ATE"

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), constrained_layout=True)
    for estimator, group in summary.groupby("estimator", sort=False):
        color = colors.get(estimator, "#34495e")
        axes[0].plot(
            group["sample_size"],
            group["bias"],
            marker="o",
            linewidth=2,
            label=labels.get(estimator, estimator),
            color=color,
        )
        axes[1].plot(
            group["sample_size"],
            group["rmse"],
            marker="o",
            linewidth=2,
            label=labels.get(estimator, estimator),
            color=color,
        )
    axes[0].axhline(0, color="#2f3747", linewidth=0.9)
    axes[0].set_title(f"Bias vs {target_label}")
    axes[0].set_ylabel("Mean estimate - known target")
    axes[1].set_title(f"RMSE vs {target_label}")
    axes[1].set_ylabel("Root mean squared error")
    for axis in axes:
        axis.set_xlabel("Sample size")
        axis.grid(alpha=0.25)
        axis.spines[["top", "right"]].set_visible(False)
    axes[1].legend(fontsize=8, frameon=False)
    bias_path = out_dir / "bias_rmse.png"
    fig.savefig(bias_path, dpi=170)
    plt.close(fig)
    paths["bias_rmse"] = bias_path.name

    fig, ax = plt.subplots(figsize=(8, 3.8), constrained_layout=True)
    for estimator, group in summary.groupby("estimator", sort=False):
        ax.plot(
            group["sample_size"],
            group["coverage"],
            marker="o",
            linewidth=2,
            label=labels.get(estimator, estimator),
            color=colors.get(estimator, "#34495e"),
        )
    ax.axhline(0.95, color="#2f3747", linestyle="--", linewidth=1, label="Nominal 95%")
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Sample size")
    ax.set_ylabel("Coverage")
    ax.set_title("95% interval coverage")
    ax.grid(alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, frameon=False)
    coverage_path = out_dir / "coverage.png"
    fig.savefig(coverage_path, dpi=170)
    plt.close(fig)
    paths["coverage"] = coverage_path.name

    example = simulate_dataset(
        contract,
        n=max(contract.sample_sizes),
        seed=contract.seed + 909_001,
    )
    treatment = contract.treatment.name
    fig, ax = plt.subplots(figsize=(8, 3.8), constrained_layout=True)
    ax.hist(
        example.loc[example[treatment] == 0, "propensity"],
        bins=26,
        alpha=0.70,
        label="A=0",
        color="#5878a8",
    )
    ax.hist(
        example.loc[example[treatment] == 1, "propensity"],
        bins=26,
        alpha=0.70,
        label="A=1",
        color="#c46a4a",
    )
    ax.set_xlabel("True propensity score from the DGP")
    ax.set_ylabel("Count")
    ax.set_title("Treatment overlap in one generated dataset")
    ax.grid(alpha=0.20)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, frameon=False)
    overlap_path = out_dir / "propensity_overlap.png"
    fig.savefig(overlap_path, dpi=170)
    plt.close(fig)
    paths["propensity_overlap"] = overlap_path.name

    heterogeneity = contract.outcome.treatment_effect_heterogeneity
    if heterogeneity.enabled and heterogeneity.modifier:
        modifier = heterogeneity.modifier
        example = example.sort_values(modifier)
        fig, ax = plt.subplots(figsize=(8, 3.4), constrained_layout=True)
        if set(example[modifier].dropna().unique()).issubset({0.0, 1.0}):
            grouped = example.groupby(modifier)["tau"].mean().reset_index()
            ax.bar(
                grouped[modifier].astype(str),
                grouped["tau"],
                color=["#5878a8", "#c46a4a"][: len(grouped)],
            )
            ax.set_xlabel(f"Effect modifier: {modifier}")
        else:
            ax.plot(example[modifier], example["tau"], color="#2f6f7e", linewidth=2)
            ax.set_xlabel(f"Effect modifier: {modifier}")
        if contract.outcome.type == "continuous":
            ax.axhline(
                contract.outcome.treatment_effect, color="#2f3747", linestyle="--", linewidth=1
            )
            ax.set_ylabel("Individual treatment effect")
        else:
            ax.axhline(example["tau"].mean(), color="#2f3747", linestyle="--", linewidth=1)
            ax.set_ylabel("Individual risk difference")
        ax.set_title("Configured treatment-effect heterogeneity")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.20, axis="y")
        hte_path = out_dir / "effect_heterogeneity.png"
        fig.savefig(hte_path, dpi=170)
        plt.close(fig)
        paths["effect_heterogeneity"] = hte_path.name

    return paths


def _contract_summary(contract: DGPContract) -> str:
    covariates = ", ".join(f"{name} ({spec.role})" for name, spec in contract.covariates.items())
    treatment_terms = ", ".join(
        f"{term}: {coef:g}" for term, coef in contract.treatment.formula.items()
    )
    outcome_terms = ", ".join(
        f"{term}: {coef:g}" for term, coef in contract.outcome.coefficients.items()
    )
    heterogeneity = contract.outcome.treatment_effect_heterogeneity
    if heterogeneity.enabled:
        heterogeneity_text = (
            f"enabled, modifier={heterogeneity.modifier}, coefficient={heterogeneity.coefficient:g}"
        )
    else:
        heterogeneity_text = "disabled"
    unobserved = contract.unobserved_confounder
    if unobserved.enabled:
        unobserved_text = (
            f"enabled, name={unobserved.name}, observed by estimators={unobserved.observed}, "
            f"A coefficient={unobserved.treatment_coefficient:g}, outcome coefficient={unobserved.outcome_coefficient:g}"
        )
    else:
        unobserved_text = "disabled"
    missing = contract.missing_data
    if missing.enabled:
        missing_text = (
            f"enabled, target={missing.target}, mechanism={missing.mechanism}, "
            f"target missing rate={missing.rate:g}, formula terms={', '.join(missing.formula) or 'none'}"
        )
    else:
        missing_text = "disabled"
    clusters = contract.clusters
    if clusters.enabled:
        cluster_confounder = clusters.cluster_level_confounder
        cluster_text = (
            f"enabled, id={clusters.cluster_id}, n_clusters={clusters.n_clusters}, "
            f"cluster_size={clusters.cluster_size}, target ICC={clusters.icc}, "
            f"ICC takes precedence over random_intercept.outcome_sd for continuous outcomes"
        )
        if cluster_confounder.enabled:
            cluster_text += (
                f", cluster confounder={cluster_confounder.name} "
                f"(A coef={cluster_confounder.treatment_coefficient:g}, Y coef={cluster_confounder.outcome_coefficient:g})"
            )
    else:
        cluster_text = "disabled"
    if contract.outcome.type == "binary":
        outcome_text = f"logistic binary; conditional treatment coefficient {contract.outcome.treatment_effect:g}"
    elif contract.outcome.type == "count":
        exposure = contract.outcome.exposure
        assert exposure is not None
        overdispersion = contract.outcome.overdispersion
        overdispersion_text = (
            f"negative-binomial overdispersion theta={overdispersion.theta:g}"
            if overdispersion.enabled
            else "Poisson variance"
        )
        outcome_text = (
            f"Poisson count/rate; conditional log-rate treatment coefficient {contract.outcome.treatment_effect:g}; "
            f"exposure={exposure.name}, distribution=lognormal(meanlog={exposure.meanlog:g}, sdlog={exposure.sdlog:g}), "
            f"reporting scale={exposure.scale:g}; {overdispersion_text}"
        )
    else:
        noise_sd = 1.0 if contract.outcome.noise_sd is None else contract.outcome.noise_sd
        outcome_text = (
            f"linear continuous; treatment effect {contract.outcome.treatment_effect:g}; "
            f"noise SD {noise_sd:g}"
        )
    return f"""
    <dl class="dgp-list">
      <dt>Schema</dt><dd>{escape(contract.schema_version)}</dd>
      <dt>Template</dt><dd>{escape(_template_label(contract.template))}</dd>
      <dt>Estimand</dt><dd>{escape(contract.estimand.name)}: {escape(contract.estimand.contrast)}; primary={escape(contract.estimand.primary)}</dd>
      <dt>Covariates</dt><dd>{escape(covariates)}</dd>
      <dt>Treatment</dt><dd>{escape(contract.treatment.assignment)} assignment; {escape(treatment_terms)}</dd>
      <dt>Outcome</dt><dd>{escape(outcome_text)}</dd>
      <dt>Outcome coefficients</dt><dd>{escape(outcome_terms)}</dd>
      <dt>Effect heterogeneity</dt><dd>{escape(heterogeneity_text)}</dd>
      <dt>Unobserved confounder</dt><dd>{escape(unobserved_text)}</dd>
      <dt>Missing data</dt><dd>{escape(missing_text)}</dd>
      <dt>Clusters</dt><dd>{escape(cluster_text)}</dd>
    </dl>
    """


def _truth_source(contract: DGPContract) -> str:
    if contract.outcome.type == "binary":
        return "Oracle Monte Carlo truth from counterfactual probabilities"
    if contract.outcome.type == "count":
        return "Oracle Monte Carlo truth from counterfactual expected counts and exposure"
    heterogeneity = contract.outcome.treatment_effect_heterogeneity
    if not heterogeneity.enabled or heterogeneity.coefficient == 0:
        return "Analytical truth from constant treatment effect"
    return "Analytical truth from configured effect heterogeneity"


def _heterogeneity_html(contract: DGPContract, truth: float) -> str:
    heterogeneity = contract.outcome.treatment_effect_heterogeneity
    if not heterogeneity.enabled:
        return ""
    if contract.outcome.type == "binary":
        return f"""
    <section>
      <h2>Effect Heterogeneity</h2>
      <p class="note">The logistic treatment coefficient varies as <code>logit_tau(X) = {contract.outcome.treatment_effect:g} + {heterogeneity.coefficient:g} * {escape(str(heterogeneity.modifier))}</code>. DGPForge benchmarks the marginal causal estimand on the probability scale, so the reported target is not this conditional logit coefficient.</p>
      <div class="cards compact-cards">
        <div class="card"><div class="label">Conditional logit baseline</div><div class="value">{contract.outcome.treatment_effect:.3f}</div></div>
        <div class="card"><div class="label">Modifier</div><div class="value">{escape(str(heterogeneity.modifier))}</div></div>
        <div class="card"><div class="label">Logit heterogeneity coefficient</div><div class="value">{heterogeneity.coefficient:.3f}</div></div>
        <div class="card"><div class="label">Known marginal target</div><div class="value">{truth:.3f}</div></div>
      </div>
    </section>
    """
    return f"""
    <section>
      <h2>Effect Heterogeneity</h2>
      <p class="note">The individual treatment effect is <code>tau(X) = {contract.outcome.treatment_effect:g} + {heterogeneity.coefficient:g} * {escape(str(heterogeneity.modifier))}</code>. The reported true ATE is the marginal average of this CATE over the generated covariate distribution, not just the baseline effect.</p>
      <div class="cards compact-cards">
        <div class="card"><div class="label">Baseline effect</div><div class="value">{contract.outcome.treatment_effect:.3f}</div></div>
        <div class="card"><div class="label">Modifier</div><div class="value">{escape(str(heterogeneity.modifier))}</div></div>
        <div class="card"><div class="label">Heterogeneity coefficient</div><div class="value">{heterogeneity.coefficient:.3f}</div></div>
        <div class="card"><div class="label">True marginal ATE</div><div class="value">{truth:.3f}</div></div>
      </div>
    </section>
    """


def _workflow_html(contract: DGPContract) -> str:
    if contract.outcome.type == "binary":
        truth_text = "Counterfactual marginal risks and risk-scale contrasts are computed from oracle probabilities."
        benchmark_text = "Binary estimators target the marginal risk difference unless another target is explicitly configured."
    elif contract.outcome.type == "count":
        truth_text = (
            "Counterfactual rates are computed as total expected counts divided by total exposure."
        )
        benchmark_text = "Count/rate estimators target the marginal rate difference; SE/CI/coverage are shown only where an approximation is implemented."
    else:
        truth_text = "ATE is computed from the configured potential-outcome model."
        benchmark_text = "Naive, adjusted OLS, IPW, AIPW, and optional misspecification variants target the same estimand."
    steps = [
        ("DGP contract", "YAML defines covariates, treatment, outcome, estimand, and seed."),
        (
            "Potential outcomes",
            "Simulator generates Y0, Y1, treatment, observed Y, and true propensity.",
        ),
        ("Known target", truth_text),
        ("Benchmarks", benchmark_text),
        ("Diagnostics", "Bias, RMSE, coverage, MCSE, overlap, and warnings close the loop."),
    ]
    items = "\n".join(
        f"""
        <div class="workflow-step">
          <div class="step-index">{index}</div>
          <div><strong>{escape(title)}</strong><span>{escape(body)}</span></div>
        </div>
        """
        for index, (title, body) in enumerate(steps, start=1)
    )
    return f'<div class="workflow">{items}</div>'


def _dag_html(contract: DGPContract) -> str:
    treatment_terms = set(contract.treatment.formula) - {"intercept"}
    confounders = [name for name in contract.covariates if name in treatment_terms]
    prognostic = [name for name in contract.covariates if name not in treatment_terms]
    confounder_label = ", ".join(confounders) if confounders else "none"
    prognostic_label = ", ".join(prognostic) if prognostic else "none"
    if contract.treatment.assignment == "randomized":
        assignment_text = "Randomized treatment: no X -> A path in the configured DGP."
        x_to_a = ""
    else:
        assignment_text = (
            "Observed treatment assignment: treatment depends on configured covariates."
        )
        x_to_a = '<line x1="190" y1="90" x2="345" y2="90" marker-end="url(#arrow)" />'

    return f"""
    <div class="dag-wrap">
      <svg viewBox="0 0 720 190" role="img" aria-label="Causal structure diagram">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z"></path>
          </marker>
        </defs>
        <rect x="24" y="54" width="166" height="72" rx="8"></rect>
        <text x="107" y="82" text-anchor="middle">Covariates X</text>
        <text x="107" y="105" text-anchor="middle">confounders: {escape(confounder_label)}</text>
        <rect x="346" y="54" width="114" height="72" rx="8"></rect>
        <text x="403" y="96" text-anchor="middle">A</text>
        <rect x="566" y="54" width="114" height="72" rx="8"></rect>
        <text x="623" y="96" text-anchor="middle">Y</text>
        {x_to_a}
        <line x1="460" y1="90" x2="566" y2="90" marker-end="url(#arrow)" />
        <path d="M 190 118 C 310 175, 455 175, 566 118" marker-end="url(#arrow)" fill="none"></path>
      </svg>
      <p>{escape(assignment_text)} Prognostic-only covariates: {escape(prognostic_label)}.</p>
    </div>
    """


def _diagnostic_table(diagnostics: pd.DataFrame) -> str:
    columns = [
        "sample_size",
        "treatment_prevalence",
        "outcome_prevalence",
        "oracle_EY1",
        "oracle_EY0",
        "observed_rate",
        "observed_rate_scaled",
        "count_mean",
        "count_variance",
        "overdispersion_ratio",
        "count_zero_fraction",
        "exposure_min",
        "exposure_median",
        "exposure_max",
        "missing_rate",
        "missing_rate_treated",
        "missing_rate_control",
        "complete_case_n",
        "fraction_rows_dropped",
        "n_clusters",
        "cluster_size_min",
        "cluster_size_median",
        "cluster_size_max",
        "target_icc",
        "empirical_icc",
        "few_clusters_warning",
        "propensity_p01",
        "propensity_p99",
        "propensity_overlap_width",
        "positivity_warning",
        "rare_outcome_warning",
        "separation_warning",
        "overdispersion_warning",
        "exposure_imbalance_warning",
    ]
    labels = {
        "sample_size": "n",
        "treatment_prevalence": "Treatment prevalence",
        "outcome_prevalence": "Outcome prevalence",
        "oracle_EY1": "Oracle EY1",
        "oracle_EY0": "Oracle EY0",
        "observed_rate": "Observed rate",
        "observed_rate_scaled": "Observed rate scaled",
        "count_mean": "Count mean",
        "count_variance": "Count variance",
        "overdispersion_ratio": "Variance / mean",
        "count_zero_fraction": "Zero fraction",
        "exposure_min": "Exposure min",
        "exposure_median": "Exposure median",
        "exposure_max": "Exposure max",
        "missing_rate": "Missing rate",
        "missing_rate_treated": "Missing A=1",
        "missing_rate_control": "Missing A=0",
        "complete_case_n": "Complete cases",
        "fraction_rows_dropped": "Rows dropped",
        "n_clusters": "Clusters",
        "cluster_size_min": "Cluster min",
        "cluster_size_median": "Cluster median",
        "cluster_size_max": "Cluster max",
        "target_icc": "Target ICC",
        "empirical_icc": "Empirical ICC",
        "few_clusters_warning": "Few clusters",
        "propensity_p01": "p-score p01",
        "propensity_p99": "p-score p99",
        "propensity_overlap_width": "Overlap width",
        "positivity_warning": "Warning",
        "rare_outcome_warning": "Rare outcome",
        "separation_warning": "Separation",
        "overdispersion_warning": "Overdispersion",
        "exposure_imbalance_warning": "Exposure imbalance",
    }
    columns = [column for column in columns if column in diagnostics.columns]
    display = diagnostics[columns].copy()
    for column in display.columns:
        display[column] = display[column].map(_format_number)
    display = display.rename(columns=labels)
    return display.to_html(index=False, escape=True, classes="data-table compact-table")


def _double_robustness_html(summary: pd.DataFrame) -> str:
    variants = {
        "aipw": ("correct", "correct"),
        "aipw_ps_misspecified": ("misspecified", "correct"),
        "aipw_outcome_misspecified": ("correct", "misspecified"),
        "aipw_double_misspecified": ("misspecified", "misspecified"),
    }
    rows = summary[summary["estimator"].isin(variants)].copy()
    misspecified_variants = set(variants) - {"aipw"}
    if rows.empty or not set(rows["estimator"]).intersection(misspecified_variants):
        return ""
    rows["ps_model"] = rows["estimator"].map(lambda name: variants[name][0])
    rows["outcome_model"] = rows["estimator"].map(lambda name: variants[name][1])
    table = rows[
        [
            "estimator",
            "ps_model",
            "outcome_model",
            "bias",
            "mcse_bias",
            "coverage",
            "mcse_coverage",
        ]
    ].copy()
    table["estimator"] = table["estimator"].map(_estimator_label)
    for column in ["bias", "mcse_bias", "coverage", "mcse_coverage"]:
        table[column] = table[column].map(_format_number)
    table = table.rename(
        columns={
            "estimator": "Estimator",
            "ps_model": "PS model",
            "outcome_model": "Outcome model",
            "bias": "Bias",
            "mcse_bias": "MCSE bias",
            "coverage": "Coverage",
            "mcse_coverage": "MCSE coverage",
        }
    )
    return f"""
    <section>
      <h2>Double Robustness Demonstration</h2>
      <p class="note">This seeded simulation compares AIPW variants with correct or deliberately misspecified nuisance models under the configured synthetic DGP and positivity conditions. One-correct variants should generally be closer to the known ATE than the double-misspecified variant here, but this is finite Monte Carlo evidence rather than a proof or universal guarantee.</p>
      <div class="table-scroll">{table.to_html(index=False, escape=True, classes="data-table compact-table")}</div>
    </section>
    """


def _binary_truth_html(contract: DGPContract, details: dict[str, float | str]) -> str:
    if contract.outcome.type != "binary":
        return ""
    return f"""
    <section>
      <h2>Binary Outcome Marginal Estimands</h2>
      <p class="note">The logistic treatment coefficient is a conditional model parameter. DGPForge benchmarks estimators against the marginal causal estimand on the probability scale.</p>
      <div class="cards compact-cards">
        <div class="card"><div class="label">True E[Y(1)]</div><div class="value">{float(details['true_EY1']):.3f}</div></div>
        <div class="card"><div class="label">True E[Y(0)]</div><div class="value">{float(details['true_EY0']):.3f}</div></div>
        <div class="card"><div class="label">Risk difference</div><div class="value">{float(details['true_risk_difference']):.3f}</div><div class="subvalue">primary benchmark target</div></div>
        <div class="card"><div class="label">Risk ratio</div><div class="value">{float(details['true_risk_ratio']):.3f}</div></div>
        <div class="card"><div class="label">Odds ratio</div><div class="value">{float(details['true_odds_ratio']):.3f}</div><div class="subvalue">marginal odds, not logistic coefficient</div></div>
      </div>
    </section>
    """


def _count_truth_html(contract: DGPContract, details: dict[str, float | str]) -> str:
    if contract.outcome.type != "count":
        return ""
    scale = float(details["exposure_scale"])
    return f"""
    <section>
      <h2>Count/Rate Outcome With Exposure Offset</h2>
      <p class="note">The DGP generates event counts with an observed exposure denominator. Oracle marginal rates are computed as total expected counterfactual counts divided by total exposure. The reporting scale is {scale:g}; rate cards show both the natural rate and the scaled public-health-style rate.</p>
      <div class="cards compact-cards">
        <div class="card"><div class="label">True rate A=1</div><div class="value">{float(details['true_rate_1']):.3f}</div><div class="subvalue">{float(details['true_rate_1']) * scale:.3f} per {scale:g}</div></div>
        <div class="card"><div class="label">True rate A=0</div><div class="value">{float(details['true_rate_0']):.3f}</div><div class="subvalue">{float(details['true_rate_0']) * scale:.3f} per {scale:g}</div></div>
        <div class="card"><div class="label">Rate difference</div><div class="value">{float(details['true_rate_difference']):.3f}</div><div class="subvalue">primary benchmark target</div></div>
        <div class="card"><div class="label">Rate ratio</div><div class="value">{float(details['true_rate_ratio']):.3f}</div></div>
        <div class="card"><div class="label">Log rate ratio</div><div class="value">{float(details['true_log_rate_ratio']):.3f}</div><div class="subvalue">conditional coefficient differs from this marginal contrast</div></div>
      </div>
      <p class="note">Count/rate SE/CI are reported only when an implemented approximation is available. The naive rate difference uses a simple independent Poisson rate approximation when overdispersion is disabled; offset g-computation and IPW rate intervals are left blank rather than filled with misleading uncertainty.</p>
    </section>
    """


def _missing_data_html(contract: DGPContract, diagnostics: pd.DataFrame) -> str:
    missing = contract.missing_data
    if not missing.enabled:
        return ""
    formula_terms = ", ".join(term for term in missing.formula if term != "intercept") or "none"
    missing_rate = (
        float(diagnostics["missing_rate"].mean()) if "missing_rate" in diagnostics else float("nan")
    )
    complete_cases = (
        float(diagnostics["complete_case_n"].mean())
        if "complete_case_n" in diagnostics
        else float("nan")
    )
    mnar_note = ""
    if missing.mechanism == "MNAR":
        mnar_note = '<p class="note warn">Observed-data estimators may be biased because this mechanism depends on unobserved or missing values. DGPForge reports the full-data truth; this demo does not prove MNAR recoverability.</p>'
    return f"""
    <section>
      <h2>Missing Data Mechanism</h2>
      <p class="note">Missingness is applied after full potential outcomes are generated. The observed outcome may be masked, but <code>{escape(missing.target)}_full</code> and the full-data potential outcomes remain available to the truth engine.</p>
      <div class="cards compact-cards">
        <div class="card"><div class="label">Mechanism</div><div class="value">{escape(missing.mechanism)}</div></div>
        <div class="card"><div class="label">Target</div><div class="value">{escape(missing.target)}</div></div>
        <div class="card"><div class="label">Configured rate</div><div class="value">{missing.rate:.3f}</div></div>
        <div class="card"><div class="label">Observed missing rate</div><div class="value">{missing_rate:.3f}</div></div>
        <div class="card"><div class="label">Mean complete cases</div><div class="value">{complete_cases:.0f}</div></div>
      </div>
      <p class="note">MCAR/MAR/MNAR labels are configured DGP mechanisms, not patterns inferred from real data. Missingness formula terms: {escape(formula_terms)}. Complete-case estimators use rows with observed outcomes; missingness-IPW estimators assume the observation model is adequate under the configured observed-data mechanism. MNAR settings are stress tests unless an explicit identifying strategy is added.</p>
      {mnar_note}
    </section>
    """


def _cluster_html(contract: DGPContract, diagnostics: pd.DataFrame) -> str:
    clusters = contract.clusters
    if not clusters.enabled:
        return ""
    n_clusters = (
        float(diagnostics["n_clusters"].mean()) if "n_clusters" in diagnostics else float("nan")
    )
    size_min = (
        float(diagnostics["cluster_size_min"].mean())
        if "cluster_size_min" in diagnostics
        else float("nan")
    )
    size_median = (
        float(diagnostics["cluster_size_median"].mean())
        if "cluster_size_median" in diagnostics
        else float("nan")
    )
    size_max = (
        float(diagnostics["cluster_size_max"].mean())
        if "cluster_size_max" in diagnostics
        else float("nan")
    )
    empirical_icc = (
        float(diagnostics["empirical_icc"].mean())
        if "empirical_icc" in diagnostics
        else float("nan")
    )
    target_icc = float(clusters.icc) if clusters.icc is not None else float("nan")
    return f"""
    <section>
      <h2>Clustered / Multilevel Structure</h2>
      <p class="note">The DGP nests observations in clusters and adds a continuous-outcome random intercept. Point estimates can be similar across OLS variants, while naive SEs can undercover when observations within clusters are correlated.</p>
      <div class="cards compact-cards">
        <div class="card"><div class="label">Clusters</div><div class="value">{n_clusters:.0f}</div></div>
        <div class="card"><div class="label">Cluster size</div><div class="value">{size_min:.0f}/{size_median:.0f}/{size_max:.0f}</div><div class="subvalue">min / median / max</div></div>
        <div class="card"><div class="label">Target ICC</div><div class="value">{target_icc:.3f}</div></div>
        <div class="card"><div class="label">Empirical ICC</div><div class="value">{empirical_icc:.3f}</div></div>
      </div>
      <p class="note">The configured estimand is individual-weighted over the generated population. For continuous outcomes, <code>icc</code> calibrates the outcome random-intercept variance and takes precedence over <code>random_intercept.outcome_sd</code>. The cluster-robust estimator uses a manual CR1 sandwich covariance over cluster score sums; with few clusters, coverage can be unstable.</p>
    </section>
    """


def _unobserved_confounder_html(contract: DGPContract, diagnostics: pd.DataFrame) -> str:
    unobserved = contract.unobserved_confounder
    if not unobserved.enabled:
        return ""
    u_treatment = (
        diagnostics["U_treatment_correlation"].mean()
        if "U_treatment_correlation" in diagnostics
        else float("nan")
    )
    u_outcome = (
        diagnostics["U_outcome_correlation"].mean()
        if "U_outcome_correlation" in diagnostics
        else float("nan")
    )
    observed_text = (
        "included in estimator adjustment sets"
        if unobserved.observed
        else "generated in the DGP but hidden from observed estimators"
    )
    return f"""
    <section>
      <h2>Unmeasured Confounder</h2>
      <p class="note">Latent <code>{escape(unobserved.name)}</code> is {escape(observed_text)}. The known causal target is still computed from potential outcomes, while observed estimators may be biased when this hidden variable affects both treatment and outcome.</p>
      <div class="cards compact-cards">
        <div class="card"><div class="label">U to treatment</div><div class="value">{unobserved.treatment_coefficient:.3f}</div></div>
        <div class="card"><div class="label">U to outcome</div><div class="value">{unobserved.outcome_coefficient:.3f}</div></div>
        <div class="card"><div class="label">Corr(U, A)</div><div class="value">{u_treatment:.3f}</div></div>
        <div class="card"><div class="label">Corr(U, Y)</div><div class="value">{u_outcome:.3f}</div></div>
      </div>
    </section>
    """


def _mc_precision_note(summary: pd.DataFrame) -> str:
    if "mcse_coverage" not in summary:
        return ""
    max_coverage_mcse = float(summary["mcse_coverage"].max(skipna=True))
    max_bias_mcse = float(summary["mcse_bias"].max(skipna=True))
    notes = [
        "MCSE columns quantify simulation uncertainty from the finite number of Monte Carlo replications. They are not estimator standard errors within a fitted dataset."
    ]
    if max_coverage_mcse > 0.05:
        notes.append(
            "Coverage MCSE is above 0.05 for at least one row, so coverage comparisons should be treated as coarse."
        )
    if max_bias_mcse > 0.10:
        notes.append(
            "Bias MCSE is nontrivial for at least one estimator; increasing replications would sharpen that comparison."
        )
    return f'<p class="note">{" ".join(escape(note) for note in notes)}</p>'


def _failure_notes_html(summary: pd.DataFrame) -> str:
    if "n_failed" not in summary or int(summary["n_failed"].sum()) == 0:
        return ""
    rows = []
    for _, row in summary[summary["n_failed"] > 0].iterrows():
        rows.append(
            "<li>"
            f"{escape(str(row['sample_size']))}, {escape(_estimator_label(row['estimator']))}: "
            f"{int(row['n_failed'])} failed"
            f" ({escape(str(row.get('first_error_type') or 'unknown'))}: "
            f"{escape(str(row.get('first_error_message') or 'no message'))})"
            "</li>"
        )
    return (
        '<p class="note">Estimator failures are recorded in '
        "<code>monte_carlo_results.csv</code> and summarized below.</p>"
        f"<ul>{''.join(rows)}</ul>"
    )


def _write_reproducibility_artifacts(
    contract: DGPContract,
    output_dir: Path,
    command: str,
    contract_source_path: str | Path | None,
) -> None:
    contract_path = output_dir / "contract.yaml"
    source_path = Path(contract_source_path) if contract_source_path is not None else None
    if source_path is not None and source_path.exists():
        try:
            same_path = source_path.resolve() == contract_path.resolve()
        except OSError:
            same_path = False
        if not same_path:
            contract_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        save_contract(contract, contract_path)

    reproduce_text = "\n".join(
        [
            "# Reproduce This Report",
            "",
            "From this output directory, rerun the deterministic report pipeline with:",
            "",
            "```bash",
            "dgpforge run --config contract.yaml --out .",
            "```",
            "",
            "Original command recorded when this report was generated:",
            "",
            "```bash",
            command,
            "```",
            "",
            "The command above regenerates the known-truth Monte Carlo report artifacts from the saved contract. LLM-assisted extraction, drafting, and review logs are preserved separately when those modes are used.",
            "",
        ]
    )
    (output_dir / "reproduce.md").write_text(reproduce_text, encoding="utf-8")


def generate_report(
    contract: DGPContract,
    result,
    out_dir: str | Path,
    command: str,
    assumptions_log_path: str | Path | None = None,
    contract_source_path: str | Path | None = None,
) -> Path:
    """Generate report.html and supporting figures."""
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_reproducibility_artifacts(contract, output_dir, command, contract_source_path)

    result.estimates.to_csv(output_dir / "monte_carlo_results.csv", index=False)
    result.summary.to_csv(output_dir / "estimator_summary.csv", index=False)
    result.diagnostics.to_csv(output_dir / "diagnostics.csv", index=False)

    plot_paths = _write_plots(contract, result.summary, output_dir)
    warning_rows = result.diagnostics[result.diagnostics["positivity_warning"]]
    if warning_rows.empty:
        positivity = "No major positivity warning triggered."
        warning_class = "ok"
        warning_badge = "Pass"
    else:
        positivity = str(warning_rows["positivity_message"].iloc[0])
        warning_class = "warn"
        warning_badge = "Warning"

    assumptions_html = ""
    if assumptions_log_path is not None and Path(assumptions_log_path).exists():
        assumptions_text = Path(assumptions_log_path).read_text(encoding="utf-8")
        assumptions_html = f"""
        <section>
          <h2>Assumptions Log</h2>
          <pre>{escape(assumptions_text)}</pre>
        </section>
        """

    max_sample = max(contract.sample_sizes)
    final_summary = result.summary[result.summary["sample_size"] == max_sample]
    table_columns = [
        "sample_size",
        "estimator",
        "mean_estimate",
        "bias",
        "mcse_bias",
        "rmse",
        "mcse_rmse",
        "coverage",
        "mcse_coverage",
        "n_valid",
        "n_failed",
        "n_not_applicable",
        "failure_rate",
        "non_ok_rate",
        "n_replications",
        "status_message",
    ]
    table_html = _html_table(result.summary, table_columns)
    precision_note_html = _mc_precision_note(result.summary)
    failure_note_html = _failure_notes_html(result.summary)
    heterogeneity_html = _heterogeneity_html(contract, result.truth)
    binary_truth_html = _binary_truth_html(contract, result.truth_details)
    count_truth_html = _count_truth_html(contract, result.truth_details)
    missing_data_html = _missing_data_html(contract, result.diagnostics)
    cluster_html = _cluster_html(contract, result.diagnostics)
    unobserved_html = _unobserved_confounder_html(contract, result.diagnostics)
    double_robustness_html = _double_robustness_html(result.summary)
    heterogeneity_figure_html = ""
    if "effect_heterogeneity" in plot_paths:
        heterogeneity_figure_html = (
            f'<figure><img src="{plot_paths["effect_heterogeneity"]}" '
            'alt="Effect heterogeneity plot"></figure>'
        )
    binary_outcome_note_html = ""
    if "binary_outcome_message" in result.diagnostics.columns:
        binary_outcome_note_html = f'<p class="note">{escape(str(result.diagnostics["binary_outcome_message"].iloc[0]))}</p>'
    count_outcome_note_html = ""
    if "count_outcome_message" in result.diagnostics.columns:
        count_outcome_note_html = f'<p class="note">{escape(str(result.diagnostics["count_outcome_message"].iloc[0]))}</p>'
    missing_data_note_html = ""
    if "missing_data_message" in result.diagnostics.columns:
        missing_data_note_html = (
            f'<p class="note">{escape(str(result.diagnostics["missing_data_message"].iloc[0]))}</p>'
        )
    cluster_note_html = ""
    if "cluster_message" in result.diagnostics.columns:
        cluster_note_html = (
            f'<p class="note">{escape(str(result.diagnostics["cluster_message"].iloc[0]))}</p>'
        )

    best_rmse = final_summary.sort_values("rmse").iloc[0]
    prevalence = result.diagnostics["treatment_prevalence"].mean()
    truth_source = _truth_source(contract)
    scenario = _title_case_name(contract.name)
    if contract.outcome.type == "binary":
        target_label = "Known target"
        target_subvalue = f"{contract.estimand.primary.replace('_', ' ')}; {truth_source}"
        hero_note = (
            "Bias and RMSE are computed against the configured marginal causal target. "
            "For binary outcomes, risk differences and risk ratios are standardized marginal estimands, not conditional logistic regression coefficients."
        )
        diagnostic_heading = "Positivity, Outcome, and Overlap"
    elif contract.outcome.type == "count":
        target_label = "Known target"
        target_subvalue = f"{contract.estimand.primary.replace('_', ' ')}; {truth_source}"
        hero_note = (
            "Bias and RMSE are computed against the configured marginal rate target. "
            "Exposure offsets define event-count denominators; conditional log-rate coefficients are not the same as marginal rate contrasts. "
            "Count/rate SE/CI are shown only when an implemented approximation is available."
        )
        diagnostic_heading = "Exposure, Overdispersion, and Overlap"
    else:
        target_label = "True ATE"
        target_subvalue = truth_source
        hero_note = (
            "Bias and RMSE are computed against the known ATE. Coverage is the fraction of Monte Carlo intervals containing that truth. "
            "The SEs are lightweight model or influence-style approximations for benchmarking, not a full inferential audit."
        )
        diagnostic_heading = "Positivity and Overlap"

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DGPForge Report - {escape(contract.name)}</title>
  <style>
    :root {{
      --ink: #172033;
      --muted: #5f6d82;
      --line: #d8deea;
      --panel: #f6f8fb;
      --panel-strong: #edf4f5;
      --accent: #2f6f7e;
      --accent-ink: #17424a;
      --rust: #a85d3d;
      --warn-bg: #fff2e8;
      --warn: #954817;
      --ok-bg: #eaf6ef;
      --ok: #256d49;
    }}
    * {{
      box-sizing: border-box;
    }}
    html {{
      max-width: 100%;
      overflow-x: hidden;
    }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #ffffff;
      line-height: 1.5;
      max-width: 100%;
      overflow-x: hidden;
    }}
    header {{
      background: #f7fafb;
      border-bottom: 1px solid var(--line);
    }}
    .hero {{
      width: 100%;
      max-width: 1120px;
      margin: 0 auto;
      padding: 38px 24px 28px;
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(280px, .8fr);
      gap: 26px;
      align-items: end;
    }}
    .eyebrow {{
      margin: 0 0 8px;
      color: var(--accent-ink);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0;
      font-size: 34px;
      line-height: 1.1;
      letter-spacing: 0;
    }}
    .subtitle {{
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 16px;
      max-width: 760px;
    }}
    .hero-note {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 14px 16px;
      font-size: 14px;
      color: var(--muted);
    }}
    .hero-note strong {{
      display: block;
      margin-bottom: 4px;
      color: var(--ink);
    }}
    main {{
      width: 100%;
      max-width: 1120px;
      margin: 0 auto;
      padding: 24px 24px 46px;
    }}
    p, span, h1, h2, h3, dt, dd, td, th, code {{
      overflow-wrap: anywhere;
    }}
    section {{
      margin-top: 26px;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 0 0 8px;
      font-size: 15px;
      letter-spacing: 0;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(5, minmax(140px, 1fr));
      gap: 12px;
    }}
    .compact-cards {{
      grid-template-columns: repeat(4, minmax(150px, 1fr));
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px 15px;
      background: var(--panel);
      min-height: 94px;
    }}
    .label {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .08em;
      font-weight: 800;
    }}
    .value {{
      margin-top: 6px;
      font-size: 22px;
      line-height: 1.15;
      font-weight: 800;
      overflow-wrap: anywhere;
    }}
    .subvalue {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
    }}
    .ok {{
      color: var(--ok);
    }}
    .warn {{
      color: var(--warn);
    }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 12px;
      font-weight: 800;
      line-height: 1;
    }}
    .badge.ok {{
      background: var(--ok-bg);
      color: var(--ok);
    }}
    .badge.warn {{
      background: var(--warn-bg);
      color: var(--warn);
    }}
    .workflow {{
      display: grid;
      grid-template-columns: repeat(5, minmax(150px, 1fr));
      gap: 10px;
    }}
    .workflow-step {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 12px;
      min-height: 130px;
    }}
    .workflow-step span {{
      display: block;
      margin-top: 5px;
      color: var(--muted);
      font-size: 13px;
    }}
    .step-index {{
      width: 25px;
      height: 25px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      margin-bottom: 10px;
      background: var(--panel-strong);
      color: var(--accent-ink);
      font-weight: 800;
      font-size: 12px;
    }}
    .two-column {{
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(300px, .95fr);
      gap: 16px;
      align-items: start;
    }}
    .dgp-list {{
      display: grid;
      grid-template-columns: minmax(130px, 210px) 1fr;
      gap: 8px 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: #fff;
      margin: 0;
    }}
    dt {{
      color: var(--muted);
      font-weight: 800;
    }}
    dd {{
      margin: 0;
      min-width: 0;
      overflow-wrap: anywhere;
    }}
    .dag-wrap {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 10px 12px 12px;
    }}
    .dag-wrap svg {{
      display: block;
      width: 100%;
      height: auto;
      max-height: 230px;
    }}
    .dag-wrap rect {{
      fill: #f8fafc;
      stroke: #ccd6e2;
    }}
    .dag-wrap line,
    .dag-wrap path {{
      stroke: #42566e;
      stroke-width: 2.2;
    }}
    .dag-wrap marker path {{
      fill: #42566e;
    }}
    .dag-wrap text {{
      fill: var(--ink);
      font-size: 16px;
      font-family: ui-sans-serif, system-ui, sans-serif;
    }}
    .dag-wrap text:nth-of-type(2) {{
      fill: var(--muted);
      font-size: 12px;
    }}
    .dag-wrap p,
    .note {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .table-scroll {{
      max-width: 100%;
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }}
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      min-width: 780px;
    }}
    .compact-table {{
      min-width: 620px;
    }}
    .data-table th,
    .data-table td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 9px;
      text-align: right;
      white-space: nowrap;
    }}
    .data-table th:first-child,
    .data-table td:first-child,
    .data-table th:nth-child(2),
    .data-table td:nth-child(2) {{
      text-align: left;
    }}
    .data-table th {{
      background: var(--panel);
      color: #303a4d;
      font-size: 12px;
    }}
    .plot-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(300px, 1fr));
      gap: 16px;
      align-items: start;
    }}
    figure {{
      margin: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fff;
    }}
    figure.wide {{
      grid-column: 1 / -1;
    }}
    figure img {{
      width: 100%;
      display: block;
    }}
    pre {{
      white-space: pre-wrap;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #fbfcfe;
      overflow-x: auto;
      font-size: 13px;
    }}
    code {{
      background: #eef3f7;
      padding: 2px 5px;
      border-radius: 5px;
      overflow-wrap: anywhere;
      white-space: normal;
    }}
    @media (max-width: 900px) {{
      .hero,
      main {{
        padding-left: 16px;
        padding-right: 16px;
      }}
      .hero,
      .two-column {{
        grid-template-columns: 1fr;
      }}
      .cards,
      .compact-cards,
      .workflow,
      .plot-grid {{
        grid-template-columns: 1fr;
      }}
      h1 {{
        font-size: 29px;
      }}
      .dgp-list {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="hero">
      <div>
        <p class="eyebrow">DGPForge known-truth simulation report</p>
        <h1>{escape(scenario)}</h1>
        <p class="subtitle">Synthetic-data tools generate data that look real. DGPForge generates data whose truth is known, then asks whether candidate estimators recover that truth.</p>
      </div>
      <div class="hero-note">
        <strong>How to read this report</strong>
        {escape(hero_note)}
      </div>
    </div>
  </header>
  <main>
    <section class="cards" aria-label="Summary cards">
      <div class="card"><div class="label">{escape(target_label)}</div><div class="value">{result.truth:.3f}</div><div class="subvalue">{escape(target_subvalue)}</div></div>
      <div class="card"><div class="label">Sample sizes</div><div class="value">{escape(', '.join(map(str, contract.sample_sizes)))}</div><div class="subvalue">per Monte Carlo grid</div></div>
      <div class="card"><div class="label">Replications</div><div class="value">{contract.n_replications}</div><div class="subvalue">per sample size</div></div>
      <div class="card"><div class="label">Treatment prevalence</div><div class="value">{prevalence:.3f}</div><div class="subvalue">mean across runs</div></div>
      <div class="card"><div class="label">Positivity status</div><div class="value"><span class="badge {warning_class}">{warning_badge}</span></div><div class="subvalue">{escape(positivity)}</div></div>
    </section>

    <section>
      <h2>Known-Truth Workflow</h2>
      {_workflow_html(contract)}
    </section>

    <section class="two-column">
      <div>
        <h2>DGP Summary</h2>
        {_contract_summary(contract)}
      </div>
      <div>
        <h2>Causal Structure</h2>
        {_dag_html(contract)}
      </div>
    </section>

    {heterogeneity_html}

    {binary_truth_html}

    {count_truth_html}

    {missing_data_html}

    {cluster_html}

    {unobserved_html}

    <section>
      <h2>{diagnostic_heading}</h2>
      <p class="{warning_class}"><strong>{escape(positivity)}</strong></p>
      {binary_outcome_note_html}
      {count_outcome_note_html}
      {missing_data_note_html}
      {cluster_note_html}
      <div class="table-scroll">{_diagnostic_table(result.diagnostics)}</div>
    </section>

    <section>
      <h2>Estimator Summary</h2>
      <div class="table-scroll">{table_html}</div>
      {failure_note_html}
      {precision_note_html}
      <p class="note">At the largest sample size, the lowest RMSE estimator in this run is <strong>{escape(_estimator_label(best_rmse['estimator']))}</strong>. Interpret this as scenario-specific Monte Carlo evidence, not a universal ranking.</p>
    </section>

    {double_robustness_html}

    <section>
      <h2>Plots</h2>
      <div class="plot-grid">
        <figure class="wide"><img src="{plot_paths['bias_rmse']}" alt="Bias and RMSE plot"></figure>
        <figure><img src="{plot_paths['coverage']}" alt="Coverage plot"></figure>
        <figure><img src="{plot_paths['propensity_overlap']}" alt="Propensity overlap plot"></figure>
        {heterogeneity_figure_html}
      </div>
    </section>

    {assumptions_html}

    <section>
      <h2>Reproducibility</h2>
      <p><code>{escape(command)}</code></p>
      <p class="note">This folder also includes <code>contract.yaml</code> and <code>reproduce.md</code> for self-contained deterministic reruns. Generated artifacts include <code>report.html</code>, <code>estimator_summary.csv</code>, <code>monte_carlo_results.csv</code>, <code>diagnostics.csv</code>, and the plot PNGs referenced above.</p>
    </section>
  </main>
</body>
</html>
"""
    report_path = output_dir / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return report_path
