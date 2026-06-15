"""Artifact writers shared by LLM-assisted workflows."""

from __future__ import annotations

from pathlib import Path

import yaml

from dgpforge.llm.schemas import ContractDraftResponse


def write_markdown_list(path: Path, title: str, items: list[str], empty_text: str) -> Path:
    lines = [f"# {title}", ""]
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append(empty_text)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_assumptions(
    path: Path,
    response: ContractDraftResponse,
    *,
    provider_name: str,
    mode: str,
) -> Path:
    lines = [
        "# Assumptions Log",
        "",
        f"Provider: `{provider_name}`",
        f"Mode: `{mode}`",
        "",
        "LLM-assisted mode drafts or reviews contracts only. Deterministic DGPForge modules "
        "produce truth, simulations, estimator summaries, diagnostics, and reports.",
        "",
        "## Filled Or Inferred Fields",
    ]
    if response.assumptions:
        for item in response.assumptions:
            lines.append(f"- `{item.field}` ({item.status}): `{item.value}` - {item.reason}")
    else:
        lines.append("- No filled assumptions were returned.")
    lines.extend(["", "## Confidence", response.confidence])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_source_trace(path: Path, response: ContractDraftResponse, title: str) -> Path:
    lines = [f"# {title}", ""]
    if response.source_trace:
        for item in response.source_trace:
            lines.append(f"- `{item.mapped_to}` <= {item.text}")
    else:
        lines.append("No source trace was returned.")
    lines.extend(
        [
            "",
            "This trace is provenance for a contract draft, not evidence about estimator performance.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_validation_report(path: Path, *, passed: bool, errors: str | None = None) -> Path:
    lines = [
        "# Validation Report",
        "",
        f"Status: {'PASS' if passed else 'FAIL'}",
        "",
        "Validation uses the deterministic `DGPContract` schema before any simulation can run.",
    ]
    if errors:
        lines.extend(["", "## Errors", "```text", errors.strip(), "```"])
    else:
        lines.extend(
            [
                "",
                "The draft contract passed schema validation. Statistical evidence still comes only "
                "from deterministic simulation and reporting modules.",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_agent_summary(
    path: Path,
    *,
    mode: str,
    provider_name: str,
    input_text: str,
    draft_path: Path | None,
    assumptions_path: Path | None,
    unresolved_path: Path | None,
    validation_report_path: Path,
    validation_passed: bool,
    report_path: Path | None,
    run_requested: bool,
) -> Path:
    lines = [
        "# Agent Run Summary",
        "",
        f"Mode: `{mode}`",
        f"Provider: `{provider_name}`",
        f"Validation status: `{'PASS' if validation_passed else 'FAIL'}`",
        f"Run requested: `{run_requested}`",
        "",
        "## Input",
        "```text",
        input_text.strip()[:2000],
        "```",
        "",
        "## Artifacts",
    ]
    for label, artifact in [
        ("Draft config", draft_path),
        ("Assumptions log", assumptions_path),
        ("Unresolved questions", unresolved_path),
        ("Validation report", validation_report_path),
        ("Deterministic report", report_path),
    ]:
        if artifact is not None:
            lines.append(f"- {label}: `{artifact.name}`")
    if run_requested and report_path is None:
        lines.append("- Deterministic report: not written because validation did not pass.")
    lines.extend(
        [
            "",
            "## Safeguard",
            "The provider drafted structured contract fields only. DGPForge validation, truth "
            "engines, Monte Carlo runners, diagnostics, and reports produce the statistical evidence.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_draft_yaml(path: Path, contract_data: dict[str, object]) -> Path:
    path.write_text(yaml.safe_dump(contract_data, sort_keys=False), encoding="utf-8")
    return path
