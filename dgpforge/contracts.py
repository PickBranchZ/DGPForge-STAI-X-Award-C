"""YAML contract loading and saving."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from dgpforge.schema import DGPContract


def load_contract(path: str | Path) -> DGPContract:
    """Load and validate a DGP contract from YAML."""
    contract_path = Path(path)
    data: dict[str, Any] = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
    return DGPContract.model_validate(data)


def save_contract(contract: DGPContract, path: str | Path) -> Path:
    """Write a DGP contract to YAML."""
    contract_path = Path(path)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    data = contract.model_dump(mode="json")
    contract_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return contract_path
