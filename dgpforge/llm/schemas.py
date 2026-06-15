"""Structured objects for optional LLM-assisted DGP contract workflows."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LLMAssumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    status: Literal["specified", "defaulted", "inferred", "unresolved"]
    value: Any = None
    reason: str


class SourceTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    mapped_to: str


class ContractDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dgp_contract: dict[str, Any]
    assumptions: list[LLMAssumption] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    source_trace: list[SourceTrace] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    deterministic_check: str
    llm_interpretation: str
    unresolved_decision: str | None = None


class ConfigReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    findings: list[ReviewFinding] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
