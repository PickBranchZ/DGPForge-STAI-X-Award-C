import numpy as np
import pandas as pd

from dgpforge.monte_carlo import summarize_estimates


def test_summary_reports_mc_precision_and_denominators():
    estimates = pd.DataFrame(
        {
            "sample_size": [100, 100, 100, 100],
            "estimator": ["demo", "demo", "demo", "demo"],
            "estimate": [1.0, 2.0, 3.0, 4.0],
            "se": [0.5, 0.5, 0.5, 0.5],
            "ci_lower": [0.5, 1.5, 2.5, 3.5],
            "ci_upper": [1.5, 2.5, 3.5, 4.5],
            "covered": [False, True, False, False],
        }
    )

    summary = summarize_estimates(estimates, truth=2.0).iloc[0]
    errors = np.array([-1.0, 0.0, 1.0, 2.0])

    assert summary["n_attempted"] == 4
    assert summary["n_valid"] == 4
    assert summary["failure_rate"] == 0
    assert np.isclose(summary["mcse_bias"], errors.std(ddof=1) / np.sqrt(4))
    assert np.isclose(summary["mcse_coverage"], np.sqrt(0.25 * 0.75 / 4))


def test_summary_counts_failed_estimator_runs():
    estimates = pd.DataFrame(
        {
            "sample_size": [100, 100],
            "estimator": ["demo", "demo"],
            "estimate": [2.0, np.nan],
            "se": [0.2, np.nan],
            "ci_lower": [1.6, np.nan],
            "ci_upper": [2.4, np.nan],
            "covered": [True, False],
        }
    )

    summary = summarize_estimates(estimates, truth=2.0).iloc[0]

    assert summary["n_attempted"] == 2
    assert summary["n_valid"] == 1
    assert summary["n_coverage"] == 1
    assert summary["failure_rate"] == 0.5
