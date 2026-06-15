"""Diagnostics for overlap, positivity, and Monte Carlo uncertainty."""

from __future__ import annotations

import numpy as np
import pandas as pd

from dgpforge.schema import DGPContract


def treatment_prevalence(data: pd.DataFrame, treatment_name: str = "A") -> float:
    return float(data[treatment_name].mean())


def propensity_overlap(data: pd.DataFrame, treatment_name: str = "A") -> dict[str, float]:
    propensity = data["propensity"].to_numpy(dtype=float)
    treatment = data[treatment_name].to_numpy(dtype=float)
    treated_propensity = propensity[treatment == 1]
    control_propensity = propensity[treatment == 0]

    def quantile(values: np.ndarray, q: float) -> float:
        if len(values) == 0:
            return float("nan")
        return float(np.quantile(values, q))

    treated_p05 = quantile(treated_propensity, 0.05)
    treated_p95 = quantile(treated_propensity, 0.95)
    control_p05 = quantile(control_propensity, 0.05)
    control_p95 = quantile(control_propensity, 0.95)
    if np.isfinite([treated_p05, treated_p95, control_p05, control_p95]).all():
        overlap_width = min(treated_p95, control_p95) - max(treated_p05, control_p05)
    else:
        overlap_width = float("nan")

    return {
        "propensity_min": float(np.min(propensity)),
        "propensity_p01": float(np.quantile(propensity, 0.01)),
        "propensity_p05": float(np.quantile(propensity, 0.05)),
        "propensity_median": float(np.quantile(propensity, 0.50)),
        "propensity_p95": float(np.quantile(propensity, 0.95)),
        "propensity_p99": float(np.quantile(propensity, 0.99)),
        "propensity_max": float(np.max(propensity)),
        "treated_propensity_p05": treated_p05,
        "treated_propensity_p95": treated_p95,
        "control_propensity_p05": control_p05,
        "control_propensity_p95": control_p95,
        "propensity_overlap_width": float(overlap_width),
    }


def positivity_warning(overlap: dict[str, float]) -> tuple[bool, str]:
    low_tail = overlap["propensity_p01"] < 0.05
    high_tail = overlap["propensity_p99"] > 0.95
    missing_arm = not np.isfinite(overlap["propensity_overlap_width"])
    separated_central_ranges = not missing_arm and overlap["propensity_overlap_width"] < 0

    messages = []
    if low_tail:
        messages.append("propensity 1st percentile is below 0.05")
    if high_tail:
        messages.append("propensity 99th percentile is above 0.95")
    if missing_arm:
        messages.append("one treatment arm is absent, so overlap is undefined")
    if separated_central_ranges:
        messages.append("treated/control central propensity ranges do not overlap")

    if not messages:
        return False, "No major positivity warning triggered."
    return True, "; ".join(messages) + "."


def _empirical_icc(data: pd.DataFrame, outcome_name: str, cluster_id: str) -> float:
    observed = data[[outcome_name, cluster_id]].dropna()
    if observed.empty:
        return float("nan")
    groups = observed.groupby(cluster_id)[outcome_name]
    sizes = groups.size()
    if len(sizes) < 2:
        return float("nan")
    means = groups.mean()
    grand_mean = float(observed[outcome_name].mean())
    ss_between = float((sizes * (means - grand_mean) ** 2).sum())
    ss_within = float(groups.apply(lambda values: ((values - values.mean()) ** 2).sum()).sum())
    ms_between = ss_between / max(len(sizes) - 1, 1)
    ms_within = ss_within / max(len(observed) - len(sizes), 1)
    mean_size = float(sizes.mean())
    denominator = ms_between + (mean_size - 1.0) * ms_within
    if denominator <= 0:
        return float("nan")
    return float((ms_between - ms_within) / denominator)


def diagnostics_for_dataset(
    data: pd.DataFrame, contract: DGPContract
) -> dict[str, float | str | bool]:
    overlap = propensity_overlap(data, treatment_name=contract.treatment.name)
    warning, warning_message = positivity_warning(overlap)
    diagnostics: dict[str, float | str | bool] = {
        "treatment_prevalence": treatment_prevalence(data, treatment_name=contract.treatment.name),
        **overlap,
        "positivity_warning": warning,
        "positivity_message": warning_message,
        "unobserved_confounder_enabled": contract.unobserved_confounder.enabled,
        "unobserved_confounder_observed": contract.unobserved_confounder.observed,
    }
    if contract.clusters.enabled:
        cluster_id = contract.clusters.cluster_id
        cluster_sizes = data.groupby(cluster_id).size()
        n_clusters = int(cluster_sizes.size)
        few_cluster_warning = n_clusters < 30
        diagnostics.update(
            {
                "clusters_enabled": True,
                "n_clusters": n_clusters,
                "cluster_size_min": int(cluster_sizes.min()),
                "cluster_size_median": float(cluster_sizes.median()),
                "cluster_size_max": int(cluster_sizes.max()),
                "target_icc": (
                    float(contract.clusters.icc)
                    if contract.clusters.icc is not None
                    else float("nan")
                ),
                "cluster_outcome_sd": (
                    float(data["_cluster_outcome_intercept"].std(ddof=1))
                    if "_cluster_outcome_intercept" in data and n_clusters > 1
                    else float("nan")
                ),
                "empirical_icc": _empirical_icc(data, contract.outcome.name, cluster_id),
                "few_clusters_warning": few_cluster_warning,
                "cluster_message": (
                    "Fewer than 30 clusters; CR1 cluster-robust coverage may be fragile."
                    if few_cluster_warning
                    else "Cluster count is adequate for this smoke demo; CR1 cluster-robust SEs are still finite-sample approximations."
                ),
            }
        )
    if contract.missing_data.enabled:
        target = contract.missing_data.target
        indicator_name = f"{contract.missing_data.missing_indicator_prefix}_{target}"
        observed = data[indicator_name].to_numpy(dtype=float)
        treatment = data[contract.treatment.name].to_numpy(dtype=float)
        treated = treatment == 1
        control = treatment == 0
        missing_rate = float(1.0 - observed.mean())
        treated_missing = float(1.0 - observed[treated].mean()) if treated.any() else float("nan")
        control_missing = float(1.0 - observed[control].mean()) if control.any() else float("nan")
        mechanism = contract.missing_data.mechanism
        diagnostics.update(
            {
                "missing_data_enabled": True,
                "missing_data_target": target,
                "missing_data_mechanism": mechanism,
                "missing_rate": missing_rate,
                "missing_rate_treated": treated_missing,
                "missing_rate_control": control_missing,
                "complete_case_n": int(observed.sum()),
                "fraction_rows_dropped": missing_rate,
                "missingness_mnar_warning": mechanism == "MNAR",
                "missing_data_message": (
                    "Observed-data estimators may be biased because missingness depends on unobserved or missing values."
                    if mechanism == "MNAR"
                    else "Missingness mechanism is configured explicitly; full-data truth remains the benchmark target."
                ),
            }
        )
    if contract.outcome.type == "binary":
        observed_mask = data[contract.outcome.name].notna().to_numpy()
        outcome = data.loc[observed_mask, contract.outcome.name].to_numpy(dtype=float)
        treatment = data.loc[observed_mask, contract.treatment.name].to_numpy(dtype=float)
        outcome_prevalence = float(outcome.mean()) if len(outcome) else float("nan")
        ey1 = float(data["p1"].mean())
        ey0 = float(data["p0"].mean())
        rare_warning = (
            np.isfinite(outcome_prevalence)
            and outcome_prevalence < 0.05
            or outcome_prevalence > 0.95
            or ey1 < 0.05
            or ey1 > 0.95
            or ey0 < 0.05
            or ey0 > 0.95
        )
        separation_warning = False
        for arm in [0.0, 1.0]:
            arm_outcome = outcome[treatment == arm]
            if len(arm_outcome) and len(np.unique(arm_outcome)) < 2:
                separation_warning = True
        extreme_probability_warning = bool(
            min(float(data["p0"].min()), float(data["p1"].min())) < 0.02
            or max(float(data["p0"].max()), float(data["p1"].max())) > 0.98
        )
        messages = []
        if rare_warning:
            messages.append("binary outcome prevalence or counterfactual risk is near the boundary")
        if separation_warning:
            messages.append("one treatment arm has a single observed outcome class")
        if extreme_probability_warning:
            messages.append("oracle outcome probabilities include extreme values")
        diagnostics.update(
            {
                "outcome_prevalence": outcome_prevalence,
                "oracle_EY1": ey1,
                "oracle_EY0": ey0,
                "rare_outcome_warning": rare_warning,
                "separation_warning": separation_warning,
                "extreme_probability_warning": extreme_probability_warning,
                "binary_outcome_message": (
                    "; ".join(messages) + "."
                    if messages
                    else "No major binary-outcome warning triggered."
                ),
            }
        )
    if contract.outcome.type == "count":
        exposure_spec = contract.outcome.exposure
        assert exposure_spec is not None
        exposure_name = exposure_spec.name
        observed_mask = data[contract.outcome.name].notna().to_numpy()
        exposure = data.loc[observed_mask, exposure_name].to_numpy(dtype=float)
        outcome = data.loc[observed_mask, contract.outcome.name].to_numpy(dtype=float)
        if len(outcome) == 0:
            exposure = data[exposure_name].to_numpy(dtype=float)
            outcome = np.array([], dtype=float)
        outcome_mean = float(outcome.mean()) if len(outcome) else float("nan")
        outcome_variance = float(outcome.var(ddof=1)) if len(outcome) > 1 else 0.0
        overdispersion_ratio = (
            outcome_variance / outcome_mean if outcome_mean > 1e-12 else float("nan")
        )
        exposure_median = float(np.median(exposure))
        exposure_min = float(np.min(exposure))
        exposure_max = float(np.max(exposure))
        exposure_imbalance_ratio = (
            exposure_max / exposure_min if exposure_min > 1e-12 else float("inf")
        )
        observed_rate = (
            float(outcome.sum() / exposure.sum()) if exposure.sum() > 0 else float("nan")
        )
        overdispersion_warning = bool(
            np.isfinite(overdispersion_ratio) and overdispersion_ratio > 3.0
        )
        exposure_imbalance_warning = bool(exposure_imbalance_ratio > 50.0)
        messages = []
        if overdispersion_warning:
            messages.append("outcome variance is much larger than the mean")
        if exposure_imbalance_warning:
            messages.append("exposure denominators are highly imbalanced")
        diagnostics.update(
            {
                "exposure_min": exposure_min,
                "exposure_median": exposure_median,
                "exposure_max": exposure_max,
                "exposure_scale": float(exposure_spec.scale),
                "observed_rate": observed_rate,
                "observed_rate_scaled": observed_rate * float(exposure_spec.scale),
                "count_mean": outcome_mean,
                "count_variance": outcome_variance,
                "overdispersion_ratio": float(overdispersion_ratio),
                "count_zero_fraction": float((outcome == 0).mean()),
                "overdispersion_warning": overdispersion_warning,
                "exposure_imbalance_warning": exposure_imbalance_warning,
                "count_outcome_message": (
                    "; ".join(messages) + "."
                    if messages
                    else "No major count/rate warning triggered."
                ),
            }
        )
    if contract.unobserved_confounder.enabled:
        name = contract.unobserved_confounder.name
        u_values = data[name].to_numpy(dtype=float)
        treatment = data[contract.treatment.name].to_numpy(dtype=float)
        outcome_name = (
            f"{contract.outcome.name}_full"
            if f"{contract.outcome.name}_full" in data
            else contract.outcome.name
        )
        outcome = data[outcome_name].to_numpy(dtype=float)

        def corr(left: np.ndarray, right: np.ndarray) -> float:
            if left.std(ddof=1) == 0 or right.std(ddof=1) == 0:
                return float("nan")
            return float(np.corrcoef(left, right)[0, 1])

        diagnostics.update(
            {
                "U_treatment_coefficient": contract.unobserved_confounder.treatment_coefficient,
                "U_outcome_coefficient": contract.unobserved_confounder.outcome_coefficient,
                "U_treatment_correlation": corr(u_values, treatment),
                "U_outcome_correlation": corr(u_values, outcome),
            }
        )
    return diagnostics


def monte_carlo_standard_error(values: pd.Series) -> float:
    return float(values.std(ddof=1) / np.sqrt(len(values)))


def summarize_diagnostics(diagnostics: pd.DataFrame) -> pd.DataFrame:
    metadata_columns = {"replication", "seed"}
    numeric_columns = [
        column
        for column in diagnostics.select_dtypes(include=["number"]).columns.tolist()
        if column not in metadata_columns and column != "sample_size"
    ]
    summary = diagnostics.groupby("sample_size", as_index=False)[numeric_columns].mean()
    warning_columns = [
        column
        for column in [
            "positivity_warning",
            "rare_outcome_warning",
            "separation_warning",
            "extreme_probability_warning",
            "overdispersion_warning",
            "exposure_imbalance_warning",
            "missing_data_enabled",
            "missingness_mnar_warning",
            "clusters_enabled",
            "few_clusters_warning",
            "unobserved_confounder_enabled",
            "unobserved_confounder_observed",
        ]
        if column in diagnostics.columns
    ]
    for column in warning_columns:
        summary = summary.merge(
            diagnostics.groupby("sample_size")[column].any().reset_index(),
            on="sample_size",
        )
    message_columns = [
        column
        for column in [
            "positivity_message",
            "binary_outcome_message",
            "count_outcome_message",
            "missing_data_message",
            "cluster_message",
        ]
        if column in diagnostics.columns
    ]
    for column in message_columns:
        messages = (
            diagnostics.groupby("sample_size")[column]
            .agg(
                lambda values: next(
                    (value for value in values if "No major" not in value), values.iloc[0]
                )
            )
            .reset_index()
        )
        summary = summary.merge(messages, on="sample_size")
    return summary
