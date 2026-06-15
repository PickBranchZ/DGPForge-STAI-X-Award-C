"""Human-readable labels for reports."""

from __future__ import annotations

import re


ESTIMATOR_LABELS = {
    "naive_difference": "Naive",
    "adjusted_ols": "Adjusted OLS",
    "adjusted_ols_omit_confounder": "Adjusted OLS, omitted confounders",
    "ipw": "IPW",
    "ipw_omit_confounder": "IPW, omitted confounders",
    "aipw": "AIPW",
    "aipw_ps_misspecified": "AIPW, PS misspecified",
    "aipw_outcome_misspecified": "AIPW, outcome misspecified",
    "aipw_double_misspecified": "AIPW, both misspecified",
    "naive_risk_difference": "Naive RD",
    "logistic_gcomp_risk_difference": "Logistic g-comp RD",
    "ipw_risk_difference": "IPW RD",
    "aipw_risk_difference": "AIPW RD",
    "adjusted_oracle_includes_U": "Oracle adjusted incl. U",
    "naive_rate_difference": "Naive rate diff.",
    "poisson_offset_gcomp_rate_difference": "Poisson offset g-comp",
    "ipw_rate_difference": "IPW rate diff.",
    "naive_difference_complete_case": "Naive complete case",
    "adjusted_ols_complete_case": "Adjusted OLS complete case",
    "aipw_complete_case": "AIPW complete case",
    "adjusted_ols_missingness_ipw": "Missingness-IPW OLS",
    "logistic_gcomp_complete_case": "Logistic g-comp complete case",
    "rate_gcomp_complete_case": "Rate g-comp complete case",
    "adjusted_ols_naive_se": "Adjusted OLS naive SE",
    "adjusted_ols_cluster_robust": "Adjusted OLS cluster-robust",
}


ACRONYM_TOKENS = {
    "A",
    "AIPW",
    "ATE",
    "CI",
    "DGP",
    "HTML",
    "ICC",
    "IPW",
    "LLM",
    "MCSE",
    "RD",
    "RMSE",
    "SE",
    "U",
    "X",
    "Y",
    "YAML",
}


def estimator_label(name: object) -> str:
    return ESTIMATOR_LABELS.get(str(name), str(name).replace("_", " "))


def title_case_name(name: str) -> str:
    words = name.replace("_", " ").strip().title().split()
    fixed_words = []
    for word in words:
        bare = word.strip("()[]{}.,:;")
        upper = bare.upper()
        if upper in ACRONYM_TOKENS or re.fullmatch(r"[AXYU]\d*", upper):
            word = word.replace(bare, upper, 1)
        fixed_words.append(word)
    return " ".join(fixed_words)


def template_label(template: str) -> str:
    labels = {
        "cross_sectional_binary_treatment_continuous_outcome": (
            "Cross-sectional binary treatment, continuous outcome"
        ),
        "cross_sectional_binary_treatment_binary_outcome": (
            "Cross-sectional binary treatment, binary outcome"
        ),
        "cross_sectional_binary_treatment_count_outcome": (
            "Cross-sectional binary treatment, count/rate outcome"
        ),
    }
    return labels.get(template, template)
