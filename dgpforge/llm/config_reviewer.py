"""LLM-assisted review of existing DGPForge configs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from dgpforge.contracts import load_contract
from dgpforge.schema import DGPContract
from dgpforge.llm.providers import LLMProvider, get_provider
from dgpforge.llm.schemas import ConfigReviewResponse, ReviewFinding


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _truth_engine(contract: DGPContract) -> str:
    if contract.outcome.type == "binary":
        return "oracle Monte Carlo over counterfactual probabilities"
    if contract.outcome.type == "count":
        return "oracle marginal rates from expected counts and exposure"
    return "analytical continuous-outcome ATE"


def _se_ci_status(contract: DGPContract) -> str:
    if contract.outcome.type == "count":
        return (
            "naive rate difference has independent Poisson rate SE when overdispersion is disabled; "
            "offset g-computation and IPW rate intervals stay blank unless implemented"
        )
    if contract.clusters.enabled:
        return "adjusted OLS naive SE and manual CR1 cluster-robust sandwich SE are available"
    if contract.missing_data.enabled:
        return "complete-case estimators reuse available intervals; missingness-IPW OLS SE/CI are blank"
    if contract.outcome.type == "binary":
        return "binary risk estimators expose lightweight implemented intervals where available"
    return (
        "continuous estimators expose lightweight OLS or influence-style intervals where available"
    )


def deterministic_checks_for_config(config_path: str | Path) -> dict[str, Any]:
    """Run deterministic validation and static review checks for a config."""
    path = Path(config_path)
    checks: dict[str, Any] = {
        "config_path": _display_path(path),
        "validation_status": "not_run",
        "validation_errors": [],
    }
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        checks["validation_status"] = "fail"
        checks["validation_errors"] = [str(exc)]
        return checks
    try:
        contract = load_contract(path)
    except (ValidationError, ValueError, OSError, yaml.YAMLError) as exc:
        checks["validation_status"] = "fail"
        checks["validation_errors"] = [str(exc)]
        return checks

    treatment_terms = {
        key: value for key, value in contract.treatment.formula.items() if key != "intercept"
    }
    weak_overlap_risk = any(abs(float(value)) >= 1.5 for value in treatment_terms.values())
    checks.update(
        {
            "validation_status": "pass",
            "schema_version": contract.schema_version,
            "name": contract.name,
            "template": contract.template,
            "outcome_type": contract.outcome.type,
            "estimand": contract.estimand.model_dump(mode="json"),
            "truth_engine": _truth_engine(contract),
            "estimators": list(contract.estimators),
            "estimator_compatibility": "schema accepted estimator names for this contract",
            "se_ci_status": _se_ci_status(contract),
            "sample_sizes": contract.sample_sizes,
            "n_replications": contract.n_replications,
            "low_replication_warning": contract.n_replications < 30,
            "weak_overlap_risk": weak_overlap_risk,
            "missingness_assumptions": contract.missing_data.model_dump(mode="json"),
            "unobserved_confounding": contract.unobserved_confounder.model_dump(mode="json"),
            "clustering": contract.clusters.model_dump(mode="json"),
            "calibration_target_caveat": "calibration configs are reviewed through dgpforge calibrate, not this DGP contract review",
        }
    )
    if raw.get("calibration"):
        checks["calibration_target_caveat"] = (
            "This file includes a calibration block; review calibration outputs for target-vs-achieved checks."
        )
    return checks


def _write_deterministic_checks_md(path: Path, checks: dict[str, Any]) -> Path:
    lines = ["# Deterministic Checks", ""]
    for key, value in checks.items():
        rendered = (
            json.dumps(value, indent=2, sort_keys=True)
            if isinstance(value, (dict, list))
            else str(value)
        )
        lines.append(f"- **{key}**: `{rendered}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_review_report(
    path: Path,
    response: ConfigReviewResponse,
    *,
    provider_name: str,
    checks: dict[str, Any],
) -> Path:
    lines = [
        "# LLM-Assisted Config Review",
        "",
        f"Provider: `{provider_name}`",
        "",
        "The LLM organizes review findings only. It does not compute truth, estimator performance, coverage, or diagnostics.",
        "",
        "## Deterministic Checks",
        "",
        f"- Validation status: `{checks.get('validation_status')}`",
        f"- Truth engine: `{checks.get('truth_engine', 'not available')}`",
        f"- SE/CI status: `{checks.get('se_ci_status', 'not available')}`",
        f"- Low replication warning: `{checks.get('low_replication_warning', 'not available')}`",
        f"- Weak overlap risk: `{checks.get('weak_overlap_risk', 'not available')}`",
        "",
        "## LLM Interpretation",
        "",
        response.summary,
        "",
    ]
    for finding in response.findings:
        lines.extend(
            [
                f"### {finding.topic}",
                "",
                f"- Deterministic check: {finding.deterministic_check}",
                f"- LLM interpretation: {finding.llm_interpretation}",
            ]
        )
        if finding.unresolved_decision:
            lines.append(f"- Unresolved decision: {finding.unresolved_decision}")
        lines.append("")
    lines.extend(
        [
            "## Safeguard",
            "",
            "Do not treat this review as statistical evidence. Run the deterministic DGPForge pipeline for truth, Monte Carlo summaries, diagnostics, and report artifacts.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _provider_failure_review(error: Exception) -> ConfigReviewResponse:
    return ConfigReviewResponse(
        summary=(
            "Provider review response failed structured validation. "
            "Only deterministic checks should be used until the provider adapter is corrected."
        ),
        findings=[
            ReviewFinding(
                topic="Provider response validation",
                deterministic_check="Deterministic checks were written before provider interpretation.",
                llm_interpretation=f"Provider output was rejected: {error}",
                unresolved_decision="Fix the provider adapter or use --provider mock.",
            )
        ],
        suggested_questions=[
            "Does the provider adapter return the ConfigReviewResponse schema?",
            "Can the deterministic report be run before relying on review narration?",
        ],
    )


def run_review_workflow(
    config_path: str | Path,
    out_dir: str | Path,
    *,
    provider_name: str = "mock",
    provider: LLMProvider | None = None,
) -> Path:
    """Review a config with deterministic checks plus optional LLM organization."""
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    provider = provider or get_provider(provider_name)
    provider_name = provider.name
    checks = deterministic_checks_for_config(config_path)

    checks_json_path = output_dir / "deterministic_checks.json"
    checks_json_path.write_text(json.dumps(checks, indent=2, sort_keys=True), encoding="utf-8")
    _write_deterministic_checks_md(output_dir / "deterministic_checks.md", checks)

    try:
        raw_config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        raw_config = {}
    try:
        review = ConfigReviewResponse.model_validate(provider.review_contract(raw_config, checks))
    except (ValidationError, ValueError, TypeError) as exc:
        review = _provider_failure_review(exc)
    report_path = _write_review_report(
        output_dir / "review_report.md",
        review,
        provider_name=provider_name,
        checks=checks,
    )
    suggested_path = output_dir / "suggested_questions.md"
    lines = ["# Suggested Questions", ""]
    lines.extend(f"- {item}" for item in review.suggested_questions)
    suggested_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path
