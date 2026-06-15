"""Optional LLM provider interfaces and deterministic mock provider."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Protocol


class LLMProvider(Protocol):
    """Provider protocol for optional LLM-assisted contract workflows."""

    name: str

    def draft_contract(self, prompt: str) -> dict[str, Any]:
        """Return a structured draft response for a natural-language prompt."""

    def extract_contract(self, text: str) -> dict[str, Any]:
        """Return a structured draft response for a paper simulation excerpt."""

    def review_contract(
        self, contract: dict[str, Any], deterministic_checks: dict[str, Any]
    ) -> dict[str, Any]:
        """Return structured review findings for a validated or attempted contract."""


def _continuous_contract(name: str = "llm_draft_continuous_ate") -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "name": name,
        "template": "cross_sectional_binary_treatment_continuous_outcome",
        "sample_sizes": [500],
        "n_replications": 30,
        "seed": 20260604,
        "covariates": {
            "X1": {
                "type": "continuous",
                "distribution": "normal",
                "mean": 0,
                "sd": 1,
                "role": "confounder",
            },
            "X2": {
                "type": "binary",
                "distribution": "bernoulli",
                "p": 0.4,
                "role": "confounder",
            },
            "X3": {
                "type": "continuous",
                "distribution": "normal",
                "mean": 0,
                "sd": 1,
                "role": "prognostic",
            },
        },
        "treatment": {
            "name": "A",
            "type": "binary",
            "assignment": "logistic",
            "formula": {"intercept": -0.2, "X1": 0.8, "X2": 0.5},
        },
        "outcome": {
            "name": "Y",
            "type": "continuous",
            "model": "linear",
            "treatment_effect": 1.5,
            "treatment_effect_heterogeneity": {
                "enabled": False,
                "modifier": "X1",
                "coefficient": 0.0,
            },
            "coefficients": {"intercept": 0.3, "X1": 0.8, "X2": 0.5, "X3": 0.4},
            "noise_sd": 1.0,
        },
        "estimand": {
            "name": "marginal_ATE",
            "contrast": "E[Y(1) - Y(0)]",
            "primary": "mean_difference",
        },
        "estimators": ["naive_difference", "adjusted_ols", "ipw", "aipw"],
    }


def _binary_contract() -> dict[str, Any]:
    contract = _continuous_contract("llm_draft_binary_risk")
    contract["template"] = "cross_sectional_binary_treatment_binary_outcome"
    contract["outcome"] = {
        "name": "Y",
        "type": "binary",
        "model": "logistic",
        "treatment_effect": 0.7,
        "treatment_effect_heterogeneity": {
            "enabled": False,
            "modifier": "X1",
            "coefficient": 0.0,
        },
        "coefficients": {"intercept": -1.1, "X1": 0.5, "X2": 0.4, "X3": 0.2},
        "noise_sd": None,
    }
    contract["estimand"] = {
        "name": "marginal_risk_difference",
        "contrast": "E[Y(1)] - E[Y(0)]",
        "primary": "risk_difference",
    }
    contract["estimators"] = [
        "naive_risk_difference",
        "logistic_gcomp_risk_difference",
        "ipw_risk_difference",
        "aipw_risk_difference",
    ]
    return contract


def _count_contract() -> dict[str, Any]:
    contract = _continuous_contract("llm_draft_count_rate")
    contract["template"] = "cross_sectional_binary_treatment_count_outcome"
    contract["sample_sizes"] = [500]
    contract["outcome"] = {
        "name": "Y",
        "type": "count",
        "model": "poisson",
        "exposure": {
            "name": "exposure",
            "distribution": "lognormal",
            "meanlog": 10.8,
            "sdlog": 0.35,
            "scale": 100000,
        },
        "treatment_effect": 0.35,
        "treatment_effect_heterogeneity": {
            "enabled": False,
            "modifier": "X1",
            "coefficient": 0.0,
        },
        "coefficients": {"intercept": -5.7, "X1": 0.25, "X2": 0.25, "X3": 0.2},
        "noise_sd": None,
        "overdispersion": {
            "enabled": False,
            "model": "negative_binomial",
            "theta": 5.0,
        },
    }
    contract["estimand"] = {
        "name": "marginal_rate_difference",
        "contrast": "sum(E[Y(1)]) / sum(exposure) - sum(E[Y(0)]) / sum(exposure)",
        "primary": "rate_difference",
    }
    contract["estimators"] = [
        "naive_rate_difference",
        "poisson_offset_gcomp_rate_difference",
        "ipw_rate_difference",
    ]
    return contract


def _missing_contract() -> dict[str, Any]:
    contract = _continuous_contract("llm_draft_missing_data")
    contract["missing_data"] = {
        "enabled": True,
        "target": "Y",
        "mechanism": "MAR",
        "rate": 0.25,
        "formula": {"intercept": -1.1, "A": 0.4, "X1": 0.6},
        "apply_to": ["Y"],
        "missing_indicator_prefix": "R",
    }
    contract["estimators"] = [
        "naive_difference_complete_case",
        "adjusted_ols_complete_case",
        "aipw_complete_case",
        "adjusted_ols_missingness_ipw",
    ]
    return contract


def _cluster_contract() -> dict[str, Any]:
    contract = _continuous_contract("llm_draft_clustered_icc")
    contract["sample_sizes"] = [800]
    contract["covariates"] = {
        "X1": contract["covariates"]["X1"],
        "X2": {
            "type": "continuous",
            "distribution": "normal",
            "mean": 0,
            "sd": 1,
            "role": "prognostic",
        },
    }
    contract["treatment"]["formula"] = {"intercept": -0.15, "X1": 0.5}
    contract["outcome"]["coefficients"] = {"intercept": 0.3, "X1": 0.8, "X2": 0.5}
    contract["clusters"] = {
        "enabled": True,
        "cluster_id": "cluster_id",
        "n_clusters": 40,
        "cluster_size": 20,
        "cluster_size_distribution": "fixed",
        "icc": 0.1,
        "random_intercept": {"outcome_sd": None, "treatment_sd": 0.4},
        "cluster_level_confounder": {
            "enabled": True,
            "name": "Z_cluster",
            "distribution": "normal",
            "mean": 0,
            "sd": 1,
            "treatment_coefficient": 0.3,
            "outcome_coefficient": 0.4,
        },
    }
    contract["estimators"] = ["adjusted_ols_naive_se", "adjusted_ols_cluster_robust"]
    return contract


def _with_heterogeneity(contract: dict[str, Any]) -> dict[str, Any]:
    draft = deepcopy(contract)
    draft["name"] = "llm_draft_heterogeneous_ate"
    draft["outcome"]["treatment_effect_heterogeneity"] = {
        "enabled": True,
        "modifier": "X1",
        "coefficient": 0.4,
    }
    return draft


def _contains_any(text: str, *terms: str) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)


def _assumption(field: str, value: Any, reason: str, status: str = "defaulted") -> dict[str, Any]:
    return {"field": field, "status": status, "value": value, "reason": reason}


def _draft_response(
    contract: dict[str, Any],
    *,
    confidence: str = "medium",
    source_text: str = "prompt",
    assumptions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "dgp_contract": contract,
        "assumptions": assumptions
        or [
            _assumption(
                "outcome.noise_sd",
                contract.get("outcome", {}).get("noise_sd"),
                "Residual variance was not specified; mock provider used a documented default.",
            ),
            _assumption(
                "n_replications",
                contract.get("n_replications"),
                "Monte Carlo replications were set to a small deterministic demo value.",
            ),
        ],
        "unresolved_questions": [
            "Confirm whether the chosen estimator set matches the intended analysis plan.",
            "Confirm whether the sample size and replication count are adequate for the final demo.",
        ],
        "source_trace": [
            {"text": source_text[:160], "mapped_to": "dgp_contract"},
        ],
        "confidence": confidence,
    }


class MockProvider:
    """Deterministic provider used by tests and demos."""

    name = "mock"

    def draft_contract(self, prompt: str) -> dict[str, Any]:
        lower = prompt.lower()
        if "invalid" in lower:
            return _draft_response(
                {"name": "invalid_mock_response", "template": "not_a_registered_template"},
                confidence="low",
                source_text=prompt,
                assumptions=[
                    _assumption(
                        "template",
                        "not_a_registered_template",
                        "This intentionally invalid response exercises safe validation failure.",
                        status="specified",
                    )
                ],
            )
        if _contains_any(lower, "count", "rate", "rates", "exposure", "offset"):
            return _draft_response(_count_contract(), source_text=prompt)
        if _contains_any(lower, "missing", "missingness", "mcar", "mar", "mnar"):
            return _draft_response(_missing_contract(), source_text=prompt)
        if _contains_any(lower, "cluster", "clustered", "icc", "multilevel"):
            return _draft_response(_cluster_contract(), source_text=prompt)
        if "binary outcome" in lower or _contains_any(lower, "risk"):
            return _draft_response(_binary_contract(), source_text=prompt)
        if _contains_any(lower, "calibration") or "target prevalence" in lower:
            contract = _binary_contract()
            contract["name"] = "llm_draft_calibration_base"
            return _draft_response(
                contract,
                source_text=prompt,
                assumptions=[
                    _assumption(
                        "calibration",
                        "base DGP only",
                        "Calibration requests should be run through dgpforge calibrate; this draft supplies a compatible base DGP.",
                        status="inferred",
                    )
                ],
            )
        contract = _continuous_contract()
        if "heterogeneous" in lower or "heterogeneity" in lower:
            contract = _with_heterogeneity(contract)
        return _draft_response(contract, source_text=prompt)

    def extract_contract(self, text: str) -> dict[str, Any]:
        lower = text.lower()
        if _contains_any(lower, "count", "rate", "rates", "exposure", "offset"):
            contract = _count_contract()
            contract["name"] = "paper_llm_count_rate_demo"
        elif "binary outcome" in lower or "logistic outcome" in lower or "risk difference" in lower:
            contract = _binary_contract()
            contract["name"] = "paper_llm_binary_demo"
        else:
            contract = _continuous_contract("paper_llm_causal_ate_demo")
        response = _draft_response(contract, source_text=text, confidence="medium")
        response["assumptions"].extend(
            [
                _assumption(
                    "treatment.formula.intercept",
                    contract["treatment"]["formula"].get("intercept"),
                    "Treatment intercept was not fully specified in the excerpt.",
                ),
                _assumption(
                    "n_replications",
                    contract["n_replications"],
                    "Replications were defaulted for a fast reproducible mock demo.",
                ),
            ]
        )
        return response

    def review_contract(
        self, contract: dict[str, Any], deterministic_checks: dict[str, Any]
    ) -> dict[str, Any]:
        outcome_type = deterministic_checks.get("outcome_type", "unknown")
        se_status = deterministic_checks.get("se_ci_status", "See estimator table.")
        findings = [
            {
                "topic": "Estimand clarity",
                "deterministic_check": str(deterministic_checks.get("estimand", "not available")),
                "llm_interpretation": "The contract names an estimand before simulation; deterministic truth engines compute the target.",
                "unresolved_decision": None,
            },
            {
                "topic": "Truth engine availability",
                "deterministic_check": str(
                    deterministic_checks.get("truth_engine", "not available")
                ),
                "llm_interpretation": "The LLM does not compute truth; it only explains which deterministic truth engine applies.",
                "unresolved_decision": None,
            },
            {
                "topic": "Uncertainty reporting",
                "deterministic_check": se_status,
                "llm_interpretation": "Unsupported SE/CI/coverage rows should remain blank rather than be narrated as valid.",
                "unresolved_decision": "Decide whether additional interval estimators are needed for the final study.",
            },
        ]
        if deterministic_checks.get("weak_overlap_risk"):
            findings.append(
                {
                    "topic": "Overlap",
                    "deterministic_check": "Treatment formula contains large coefficients.",
                    "llm_interpretation": "The review can flag possible overlap risk, but Monte Carlo diagnostics must verify it.",
                    "unresolved_decision": "Consider running the deterministic report before making estimator claims.",
                }
            )
        return {
            "summary": (
                f"Mock review for a {outcome_type} DGP contract. "
                "Findings are organized by the mock LLM, while validation and statistical checks are deterministic."
            ),
            "findings": findings,
            "suggested_questions": [
                "Is the estimand the scientific target you want to benchmark?",
                "Are sample sizes and replications sufficient for the presentation?",
                "Should any unsupported uncertainty rows remain blank or be replaced by a validated method?",
            ],
        }


def get_provider(name: str) -> LLMProvider:
    """Return an optional LLM provider by name."""
    if name == "mock":
        return MockProvider()
    raise RuntimeError(
        f"Provider '{name}' is not installed. Use --provider mock for reproducible demos, "
        "or add an isolated optional adapter without making it a core dependency."
    )
