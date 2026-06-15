from pathlib import Path

from dgpforge.agent import parse_paper_excerpt


ROOT = Path(__file__).resolve().parents[1]


def test_curated_parser_extracts_expected_excerpt_values(workspace_tmp_path):
    contract, assumptions_path = parse_paper_excerpt(
        ROOT / "examples" / "paper_excerpt_causal_ate.txt",
        workspace_tmp_path,
    )

    assert contract.sample_sizes == [600]
    assert contract.n_replications == 80
    assert contract.treatment.formula["intercept"] == -0.2
    assert contract.treatment.formula["X1"] == 0.8
    assert contract.treatment.formula["X2"] == 0.6
    assert contract.outcome.treatment_effect == 2.0
    assert contract.outcome.coefficients["X1"] == 1.0
    assert contract.outcome.coefficients["X2"] == 0.5
    assert contract.outcome.coefficients["X3"] == 0.5
    assert "Residual noise SD was not specified" in assumptions_path.read_text(encoding="utf-8")
