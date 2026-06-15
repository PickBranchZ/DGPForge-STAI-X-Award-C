"""Optional LLM-assisted DGP contract workflows.

This package has no required external provider dependencies. The deterministic
`MockProvider` supports tests and demos without network or API keys.
"""

from dgpforge.llm.config_reviewer import (
    deterministic_checks_for_config,
    run_review_workflow,
)
from dgpforge.llm.contract_drafter import DraftWorkflowResult, run_draft_workflow
from dgpforge.llm.paper_extractor import run_from_paper_workflow
from dgpforge.llm.providers import LLMProvider, MockProvider, get_provider
from dgpforge.llm.schemas import ConfigReviewResponse, ContractDraftResponse

__all__ = [
    "ConfigReviewResponse",
    "ContractDraftResponse",
    "DraftWorkflowResult",
    "LLMProvider",
    "MockProvider",
    "deterministic_checks_for_config",
    "get_provider",
    "run_draft_workflow",
    "run_from_paper_workflow",
    "run_review_workflow",
]
