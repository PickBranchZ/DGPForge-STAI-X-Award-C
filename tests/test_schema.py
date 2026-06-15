from pathlib import Path

import pytest
import yaml
from typing import get_args

from dgpforge.contracts import load_contract
from dgpforge.estimators import ESTIMATORS
from dgpforge.schema import (
    CROSS_SECTIONAL_ATE_TEMPLATE,
    DGPContract,
    EstimatorName,
    TEMPLATE_REGISTRY,
    TemplateName,
)


ROOT = Path(__file__).resolve().parents[1]


def test_schema_loads_valid_yaml():
    contract = load_contract(ROOT / "examples" / "causal_ate_observed_confounding.yaml")
    assert isinstance(contract, DGPContract)
    assert contract.schema_version == "1.0"
    assert contract.treatment.name == "A"


def test_schema_rejects_unsupported_schema_version(workspace_tmp_path):
    source = yaml.safe_load(
        (ROOT / "examples" / "causal_ate_observed_confounding.yaml").read_text()
    )
    source["schema_version"] = "9.9"
    bad_path = workspace_tmp_path / "bad_version.yaml"
    bad_path.write_text(yaml.safe_dump(source), encoding="utf-8")

    with pytest.raises(Exception):
        load_contract(bad_path)


def test_template_registry_matches_supported_templates():
    assert CROSS_SECTIONAL_ATE_TEMPLATE in get_args(TemplateName)
    assert set(TEMPLATE_REGISTRY) == set(get_args(TemplateName))


def test_estimator_registry_matches_schema_literal():
    assert set(ESTIMATORS) == set(get_args(EstimatorName))


def test_schema_rejects_missing_treatment_and_outcome(workspace_tmp_path):
    source = yaml.safe_load(
        (ROOT / "examples" / "causal_ate_observed_confounding.yaml").read_text()
    )
    source.pop("treatment")
    source.pop("outcome")
    bad_path = workspace_tmp_path / "bad.yaml"
    bad_path.write_text(yaml.safe_dump(source), encoding="utf-8")

    with pytest.raises(Exception):
        load_contract(bad_path)
