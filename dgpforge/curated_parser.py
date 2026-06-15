"""Deterministic curated parser for a narrow cross-sectional ATE excerpt."""

from __future__ import annotations

import re
from pathlib import Path

from dgpforge.contracts import save_contract
from dgpforge.schema import DGPContract


def _find_float(pattern: str, text: str, default: float) -> float:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return float(match.group(1)) if match else default


def _find_int(pattern: str, text: str, default: int) -> int:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else default


def _line_with(text: str, *needles: str) -> str:
    for line in text.splitlines():
        lower = line.lower()
        if all(needle.lower() in lower for needle in needles):
            return line
    return ""


def _first_group(match: re.Match[str] | None, default: str) -> str:
    if match is None:
        return default
    return next((group for group in match.groups() if group is not None), default)


def _linear_terms(line: str) -> dict[str, float]:
    terms: dict[str, float] = {}
    for coefficient, variable in re.findall(
        r"([+-]?\s*\d+(?:\.\d+)?)\s*\*?\s*(A|X\d+)",
        line,
        flags=re.IGNORECASE,
    ):
        terms[variable.upper()] = float(coefficient.replace(" ", ""))
    return terms


def parse_paper_excerpt(input_path: str | Path, out_dir: str | Path) -> tuple[DGPContract, Path]:
    """Parse a deliberately simple causal ATE excerpt into a DGP contract."""
    source = Path(input_path)
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8")

    n_match = re.search(
        r"(?:sample size\s*)?n\s*=\s*(\d+)|sample size\s+(\d+)",
        text,
        flags=re.IGNORECASE,
    )
    n = int(_first_group(n_match, "800"))
    replications = _find_int(r"(\d+)\s+(?:Monte Carlo\s+)?replications", text, 100)
    x2_p = _find_float(r"X2\s*(?:~|was)\s*Bernoulli\((0?\.\d+|1(?:\.0)?)\)", text, 0.4)

    treatment_line = _line_with(text, "logit")
    treatment_terms = _linear_terms(treatment_line)
    intercept_matches = re.findall(r"=\s*([-+]?\d+(?:\.\d+)?)", treatment_line)
    treatment_intercept = float(intercept_matches[-1]) if intercept_matches else -0.2
    treatment_x1 = treatment_terms.get("X1", 0.8)
    treatment_x2 = treatment_terms.get("X2", 0.6)

    outcome_line = _line_with(text, "outcome", "=")
    outcome_terms = _linear_terms(outcome_line)
    effect_line = _line_with(text, "treatment effect")
    treatment_effect = _find_float(
        r"(?:treatment effect|ATE|effect of treatment)\s*(?:was|=|:)\s*([-+]?\d+(?:\.\d+)?)",
        effect_line,
        outcome_terms.get("A", 2.0),
    )
    outcome_x1 = outcome_terms.get("X1", 1.0)
    outcome_x2 = outcome_terms.get("X2", 0.5)
    outcome_x3 = outcome_terms.get("X3", 0.5)

    noise_match = re.search(
        r"(?:residual|noise)\s*(?:standard deviation|sd|sigma)?[^\d+-]*([-+]?\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    assumptions: list[str] = []
    if noise_match:
        noise_sd = float(noise_match.group(1))
    else:
        noise_sd = 1.0
        assumptions.append("Residual noise SD was not specified; set noise_sd = 1.0.")

    contract = DGPContract.model_validate(
        {
            "name": "from_text_causal_ate_demo",
            "template": "cross_sectional_binary_treatment_continuous_outcome",
            "sample_sizes": [n],
            "n_replications": replications,
            "seed": 20260602,
            "covariates": {
                "X1": {
                    "type": "continuous",
                    "distribution": "normal",
                    "mean": 0,
                    "sd": 1,
                    "role": "confounder",
                },
                "X2": {
                    "type": "binary",
                    "distribution": "bernoulli",
                    "p": x2_p,
                    "role": "confounder",
                },
                "X3": {
                    "type": "continuous",
                    "distribution": "normal",
                    "mean": 0,
                    "sd": 1,
                    "role": "prognostic",
                },
            },
            "treatment": {
                "name": "A",
                "type": "binary",
                "assignment": "logistic",
                "formula": {
                    "intercept": treatment_intercept,
                    "X1": treatment_x1,
                    "X2": treatment_x2,
                },
            },
            "outcome": {
                "name": "Y",
                "type": "continuous",
                "model": "linear",
                "treatment_effect": treatment_effect,
                "treatment_effect_heterogeneity": {
                    "enabled": False,
                    "modifier": "X1",
                    "coefficient": 0.0,
                },
                "coefficients": {
                    "intercept": 0.0,
                    "X1": outcome_x1,
                    "X2": outcome_x2,
                    "X3": outcome_x3,
                },
                "noise_sd": noise_sd,
            },
            "estimand": {
                "name": "marginal_ATE",
                "contrast": "E[Y(1) - Y(0)]",
            },
            "estimators": ["naive_difference", "adjusted_ols", "ipw", "aipw"],
        }
    )

    save_contract(contract, output_dir / "contract.yaml")
    assumptions_text = [
        "# Assumptions Log",
        "",
        f"Source excerpt: {source.name}",
        "Parser scope: curated cross-sectional binary-treatment continuous-outcome ATE template.",
    ]
    if assumptions:
        assumptions_text.extend(["", "## Filled Defaults", *[f"- {item}" for item in assumptions]])
    else:
        assumptions_text.extend(["", "No underspecified required details were detected."])
    assumptions_text.extend(
        [
            "",
            "This parser proposes a DGP contract only; simulation, truth, estimators, and diagnostics are deterministic.",
        ]
    )
    assumptions_path = output_dir / "assumptions_log.md"
    assumptions_path.write_text("\n".join(assumptions_text) + "\n", encoding="utf-8")
    return contract, assumptions_path
