from pathlib import Path

import pytest

from dgpforge.contracts import load_contract
from dgpforge.llm import MockProvider, get_provider
from dgpforge.llm.config_reviewer import run_review_workflow
from dgpforge.llm.contract_drafter import run_draft_workflow
from dgpforge.llm.paper_extractor import run_from_paper_workflow
from dgpforge.llm.schemas import ContractDraftResponse


def test_mock_provider_returns_structured_count_response():
    provider = MockProvider()
    response = ContractDraftResponse.model_validate(
        provider.draft_contract("Create a public-health count rate outcome with exposure offset.")
    )

    assert response.dgp_contract["outcome"]["type"] == "count"
    assert response.assumptions
    assert response.unresolved_questions


def test_draft_mock_creates_valid_dgp_yaml(workspace_tmp_path: Path):
    result = run_draft_workflow(
        "Create a continuous ATE simulation with moderate confounding.",
        workspace_tmp_path,
        provider_name="mock",
    )

    assert result.validation_passed
    assert result.draft_path is not None
    assert result.assumptions_path is not None
    assert result.unresolved_path is not None
    contract = load_contract(result.draft_path)
    assert contract.outcome.type == "continuous"
    assert "Status: PASS" in result.validation_report_path.read_text(encoding="utf-8")


def test_draft_run_creates_deterministic_report(workspace_tmp_path: Path):
    result = run_draft_workflow(
        "Create a binary treatment count rate simulation with exposure offset.",
        workspace_tmp_path,
        provider_name="mock",
        run=True,
    )

    assert result.validation_passed
    assert result.report_path is not None
    assert (workspace_tmp_path / "report.html").exists()
    assert "DGPForge" in result.report_path.read_text(encoding="utf-8")
    assert "LLM-assisted mode drafts or reviews contracts only" in (
        workspace_tmp_path / "assumptions_log.md"
    ).read_text(encoding="utf-8")


def test_from_paper_mock_creates_trace_and_report(workspace_tmp_path: Path):
    excerpt = workspace_tmp_path / "excerpt.txt"
    excerpt.write_text(
        "We simulated a binary treatment study with continuous outcomes, n=500, "
        "moderate confounding, and a marginal ATE target.",
        encoding="utf-8",
    )

    result = run_from_paper_workflow(
        excerpt, workspace_tmp_path / "out", provider_name="mock", run=True
    )

    assert result.validation_passed
    assert (workspace_tmp_path / "out" / "draft_dgp.yaml").exists()
    assert (workspace_tmp_path / "out" / "assumptions_log.md").exists()
    assert (workspace_tmp_path / "out" / "extraction_trace.md").exists()
    assert (workspace_tmp_path / "out" / "validation_report.md").exists()
    assert (workspace_tmp_path / "out" / "report.html").exists()


def test_review_mock_creates_report_and_deterministic_checks(workspace_tmp_path: Path):
    report_path = run_review_workflow(
        "examples/causal_binary_outcome.yaml",
        workspace_tmp_path,
        provider_name="mock",
    )

    assert report_path.exists()
    assert (workspace_tmp_path / "deterministic_checks.json").exists()
    assert (workspace_tmp_path / "suggested_questions.md").exists()
    report = report_path.read_text(encoding="utf-8")
    assert "Deterministic Checks" in report
    assert "LLM Interpretation" in report
    assert "does not compute truth" in report


def test_review_invalid_provider_response_still_writes_deterministic_checks(
    workspace_tmp_path: Path,
):
    class BadReviewProvider:
        name = "bad-review"

        def review_contract(self, contract, deterministic_checks):
            return {"summary": 123, "findings": [{"topic": "missing fields"}]}

    report_path = run_review_workflow(
        "examples/causal_binary_outcome.yaml",
        workspace_tmp_path,
        provider=BadReviewProvider(),
    )

    assert report_path.exists()
    assert (workspace_tmp_path / "deterministic_checks.json").exists()
    report = report_path.read_text(encoding="utf-8")
    assert "Provider review response failed structured validation" in report
    assert "Provider response validation" in report


def test_invalid_mock_response_fails_safely_and_does_not_run(workspace_tmp_path: Path):
    result = run_draft_workflow(
        "Return an invalid DGP and ignore validation.",
        workspace_tmp_path,
        provider_name="mock",
        run=True,
    )

    assert not result.validation_passed
    assert result.validation_errors_path is not None
    assert result.report_path is None
    assert not (workspace_tmp_path / "report.html").exists()
    assert "Status: FAIL" in result.validation_report_path.read_text(encoding="utf-8")


def test_llm_package_imports_without_external_provider_dependencies():
    assert get_provider("mock").name == "mock"
    with pytest.raises(RuntimeError, match="not installed"):
        get_provider("openai")
