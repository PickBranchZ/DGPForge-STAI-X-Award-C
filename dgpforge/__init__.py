"""DGPForge: verified known-truth simulation studies."""

from dgpforge.contracts import load_contract, save_contract
from dgpforge.calibration import calibrate_contract, run_calibration
from dgpforge.grid import expand_grid, run_scenario_grid
from dgpforge.monte_carlo import MonteCarloResult, run_monte_carlo
from dgpforge.schema import (
    CROSS_SECTIONAL_ATE_TEMPLATE,
    CROSS_SECTIONAL_BINARY_OUTCOME_TEMPLATE,
    CROSS_SECTIONAL_COUNT_OUTCOME_TEMPLATE,
    SCHEMA_VERSION,
    TEMPLATE_REGISTRY,
    DGPContract,
)
from dgpforge.sensitivity import expand_sensitivity_grid, run_sensitivity_grid
from dgpforge.simulate import simulate_dataset
from dgpforge.truth import true_ate

__all__ = [
    "DGPContract",
    "CROSS_SECTIONAL_ATE_TEMPLATE",
    "CROSS_SECTIONAL_BINARY_OUTCOME_TEMPLATE",
    "CROSS_SECTIONAL_COUNT_OUTCOME_TEMPLATE",
    "MonteCarloResult",
    "SCHEMA_VERSION",
    "TEMPLATE_REGISTRY",
    "load_contract",
    "calibrate_contract",
    "expand_grid",
    "expand_sensitivity_grid",
    "run_monte_carlo",
    "run_calibration",
    "run_scenario_grid",
    "run_sensitivity_grid",
    "save_contract",
    "simulate_dataset",
    "true_ate",
]

__version__ = "0.1.0"
