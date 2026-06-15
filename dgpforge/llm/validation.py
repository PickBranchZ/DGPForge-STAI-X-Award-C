"""Validation and execution helpers for LLM-assisted workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from dgpforge.contracts import save_contract
from dgpforge.llm.schemas import ContractDraftResponse
from dgpforge.monte_carlo import run_monte_carlo
from dgpforge.report import generate_report
from dgpforge.schema import DGPContract


def validate_response(
    raw_response: dict[str, Any]
) -> tuple[ContractDraftResponse | None, str | None]:
    try:
        return ContractDraftResponse.model_validate(raw_response), None
    except ValidationError as exc:
        return None, str(exc)


def validate_contract(contract_data: dict[str, Any]) -> tuple[DGPContract | None, str | None]:
    try:
        return DGPContract.model_validate(contract_data), None
    except ValidationError as exc:
        return None, str(exc)


def run_validated_contract(
    contract: DGPContract,
    out_dir: Path,
    command: str,
    assumptions_path: Path,
) -> Path:
    save_contract(contract, out_dir / "draft_dgp.yaml")
    result = run_monte_carlo(contract)
    return generate_report(
        contract,
        result,
        out_dir=out_dir,
        command=command,
        assumptions_log_path=assumptions_path,
    )
