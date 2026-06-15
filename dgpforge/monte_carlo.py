"""Monte Carlo benchmarking for DGPForge contracts."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from dgpforge.diagnostics import diagnostics_for_dataset, summarize_diagnostics
from dgpforge.estimators import run_estimators
from dgpforge.schema import DGPContract
from dgpforge.simulate import simulate_dataset
from dgpforge.truth import truth_details


@dataclass(frozen=True)
class MonteCarloResult:
    truth: float
    truth_details: dict[str, float | str]
    estimates: pd.DataFrame
    summary: pd.DataFrame
    diagnostics: pd.DataFrame


def _replication_seed(base_seed: int, sample_index: int, replication: int) -> int:
    return int(base_seed + 100_003 * (sample_index + 1) + replication)


def summarize_estimates(estimates: pd.DataFrame, truth: float) -> pd.DataFrame:
    rows = []
    for (sample_size, estimator), group in estimates.groupby(
        ["sample_size", "estimator"], sort=False
    ):
        attempted = int(len(group))
        if "status" in group:
            statuses = group["status"]
        else:
            statuses = pd.Series(
                np.where(np.isfinite(group["estimate"]), "ok", "failed"),
                index=group.index,
            )
        failed = statuses == "failed"
        not_applicable = statuses == "not_applicable"
        valid = group[(statuses == "ok") & np.isfinite(group["estimate"])].copy()
        error = valid["estimate"] - truth
        valid_count = int(len(valid))
        failed_count = int(failed.sum())
        not_applicable_count = int(not_applicable.sum())
        non_ok_count = failed_count + not_applicable_count
        interval_valid = valid[np.isfinite(valid["ci_lower"]) & np.isfinite(valid["ci_upper"])]
        coverage_denominator = int(len(interval_valid))
        bias = float(error.mean()) if valid_count else float("nan")
        error_sd = float(error.std(ddof=1)) if valid_count > 1 else 0.0
        squared_error = error**2
        rmse = float(np.sqrt(np.mean(squared_error))) if valid_count else float("nan")
        squared_error_sd = float(squared_error.std(ddof=1)) if valid_count > 1 else 0.0
        if valid_count and np.isfinite(rmse) and rmse > 0:
            mcse_rmse = float(squared_error_sd / np.sqrt(valid_count) / (2.0 * rmse))
        elif valid_count:
            mcse_rmse = 0.0
        else:
            mcse_rmse = float("nan")
        coverage = float(interval_valid["covered"].mean()) if coverage_denominator else float("nan")
        mcse_coverage = (
            float(np.sqrt(coverage * (1.0 - coverage) / coverage_denominator))
            if coverage_denominator and np.isfinite(coverage)
            else float("nan")
        )
        failed_rows = group[failed]
        first_error_type = None
        first_error_message = None
        if not failed_rows.empty:
            if "error_type" in failed_rows:
                first_error_type = failed_rows["error_type"].dropna().astype(str).iloc[0]
            if "error_message" in failed_rows:
                first_error_message = failed_rows["error_message"].dropna().astype(str).iloc[0]
        status_message = "ok"
        if failed_count:
            status_message = f"{failed_count} failed; first error: {first_error_type or 'unknown'}"
        elif not_applicable_count:
            status_message = f"{not_applicable_count} not applicable"
        rows.append(
            {
                "sample_size": int(sample_size),
                "estimator": estimator,
                "mean_estimate": float(valid["estimate"].mean()) if valid_count else float("nan"),
                "bias": bias,
                "mcse_bias": (
                    float(error_sd / np.sqrt(valid_count)) if valid_count else float("nan")
                ),
                "rmse": rmse,
                "mcse_rmse": mcse_rmse,
                "empirical_sd": float(valid["estimate"].std(ddof=1)) if valid_count > 1 else 0.0,
                "mean_estimated_se": float(valid["se"].mean()) if valid_count else float("nan"),
                "coverage": coverage,
                "mcse_coverage": mcse_coverage,
                "n_replications": valid_count,
                "n_attempted": attempted,
                "n_valid": valid_count,
                "n_coverage": coverage_denominator,
                "n_failed": failed_count,
                "n_not_applicable": not_applicable_count,
                "n_non_ok": non_ok_count,
                "failure_rate": float(failed_count / attempted) if attempted else float("nan"),
                "non_ok_rate": float(non_ok_count / attempted) if attempted else float("nan"),
                "failure_rate_denominator": attempted,
                "first_error_type": first_error_type,
                "first_error_message": first_error_message,
                "status_message": status_message,
            }
        )
    return pd.DataFrame(rows)


def run_monte_carlo(contract: DGPContract, oracle_n: int = 100_000) -> MonteCarloResult:
    """Run the configured Monte Carlo benchmark."""
    details = truth_details(contract, oracle_n=oracle_n)
    truth = float(details["truth"])
    estimate_rows = []
    diagnostic_rows = []

    for sample_index, sample_size in enumerate(contract.sample_sizes):
        for replication in range(contract.n_replications):
            seed = _replication_seed(contract.seed, sample_index, replication)
            data = simulate_dataset(contract, n=sample_size, seed=seed)
            diagnostics = diagnostics_for_dataset(data, contract)
            diagnostics.update(
                {"sample_size": sample_size, "replication": replication, "seed": seed}
            )
            diagnostic_rows.append(diagnostics)

            estimates = run_estimators(data, contract)
            estimates["sample_size"] = sample_size
            estimates["replication"] = replication
            estimates["seed"] = seed
            estimates["truth"] = truth
            estimates["error"] = estimates["estimate"] - truth
            estimates["covered"] = (
                np.isfinite(estimates["ci_lower"])
                & np.isfinite(estimates["ci_upper"])
                & (estimates["ci_lower"] <= truth)
                & (truth <= estimates["ci_upper"])
            )
            estimates["treatment_prevalence"] = diagnostics["treatment_prevalence"]
            estimates["propensity_p01"] = diagnostics["propensity_p01"]
            estimates["propensity_p99"] = diagnostics["propensity_p99"]
            estimates["positivity_warning"] = diagnostics["positivity_warning"]
            estimate_rows.append(estimates)

    estimates_df = pd.concat(estimate_rows, ignore_index=True)
    diagnostics_df = pd.DataFrame(diagnostic_rows)
    summary = summarize_estimates(estimates_df, truth)
    diagnostics_summary = summarize_diagnostics(diagnostics_df)
    return MonteCarloResult(
        truth=truth,
        truth_details=details,
        estimates=estimates_df,
        summary=summary,
        diagnostics=diagnostics_summary,
    )
