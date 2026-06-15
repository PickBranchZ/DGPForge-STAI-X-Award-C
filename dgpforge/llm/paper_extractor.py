"""Paper simulation excerpt to validated DGP contract draft workflow."""

from __future__ import annotations

from pathlib import Path

from dgpforge.llm.artifacts import (
    write_agent_summary,
    write_assumptions,
    write_draft_yaml,
    write_markdown_list,
    write_source_trace,
    write_validation_report,
)
from dgpforge.llm.contract_drafter import DraftWorkflowResult
from dgpforge.llm.providers import LLMProvider, get_provider
from dgpforge.llm.validation import run_validated_contract, validate_contract, validate_response


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def run_from_paper_workflow(
    input_path: str | Path,
    out_dir: str | Path,
    *,
    provider_name: str = "mock",
    provider: LLMProvider | None = None,
    run: bool = False,
    command: str | None = None,
) -> DraftWorkflowResult:
    """Extract, validate, and optionally run a DGP contract from a text excerpt."""
    source = Path(input_path)
    excerpt = source.read_text(encoding="utf-8")
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    provider = provider or get_provider(provider_name)
    provider_name = provider.name
    source_label = _display_path(source)
    command = (
        command
        or f"dgpforge from-paper --provider {provider_name} --input {source} --out {output_dir}"
    )

    validation_report_path = output_dir / "validation_report.md"
    validation_errors_path: Path | None = None
    agent_summary_path = output_dir / "agent_run_summary.md"

    response, response_errors = validate_response(provider.extract_contract(excerpt))
    if response is None:
        validation_errors_path = output_dir / "validation_errors.md"
        validation_errors_path.write_text(
            response_errors or "Invalid provider response.", encoding="utf-8"
        )
        write_validation_report(validation_report_path, passed=False, errors=response_errors)
        write_agent_summary(
            agent_summary_path,
            mode="from-paper",
            provider_name=provider_name,
            input_text=f"{source_label}\n\n{excerpt}",
            draft_path=None,
            assumptions_path=None,
            unresolved_path=None,
            validation_report_path=validation_report_path,
            validation_passed=False,
            report_path=None,
            run_requested=run,
        )
        return DraftWorkflowResult(
            output_dir,
            None,
            None,
            None,
            validation_report_path,
            validation_errors_path,
            agent_summary_path,
            None,
            False,
        )

    draft_path = write_draft_yaml(output_dir / "draft_dgp.yaml", response.dgp_contract)
    assumptions_path = write_assumptions(
        output_dir / "assumptions_log.md",
        response,
        provider_name=provider_name,
        mode="from-paper",
    )
    unresolved_path = write_markdown_list(
        output_dir / "unresolved_questions.md",
        "Unresolved Questions",
        response.unresolved_questions,
        "No unresolved questions were returned.",
    )
    write_source_trace(output_dir / "extraction_trace.md", response, "Extraction Trace")

    contract, contract_errors = validate_contract(response.dgp_contract)
    validation_passed = contract is not None
    if validation_passed:
        write_validation_report(validation_report_path, passed=True)
    else:
        validation_errors_path = output_dir / "validation_errors.md"
        validation_errors_path.write_text(contract_errors or "Invalid contract.", encoding="utf-8")
        write_validation_report(validation_report_path, passed=False, errors=contract_errors)

    report_path = None
    if run and contract is not None:
        report_path = run_validated_contract(contract, output_dir, command, assumptions_path)

    write_agent_summary(
        agent_summary_path,
        mode="from-paper",
        provider_name=provider_name,
        input_text=f"{source_label}\n\n{excerpt}",
        draft_path=draft_path,
        assumptions_path=assumptions_path,
        unresolved_path=unresolved_path,
        validation_report_path=validation_report_path,
        validation_passed=validation_passed,
        report_path=report_path,
        run_requested=run,
    )

    return DraftWorkflowResult(
        output_dir,
        draft_path,
        assumptions_path,
        unresolved_path,
        validation_report_path,
        validation_errors_path,
        agent_summary_path,
        report_path,
        validation_passed,
    )
