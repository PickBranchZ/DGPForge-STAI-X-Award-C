# LLM-Assisted Config Review

Provider: `mock`

The LLM organizes review findings only. It does not compute truth, estimator performance, coverage, or diagnostics.

## Deterministic Checks

- Validation status: `pass`
- Truth engine: `oracle Monte Carlo over counterfactual probabilities`
- SE/CI status: `binary risk estimators expose lightweight implemented intervals where available`
- Low replication warning: `False`
- Weak overlap risk: `False`

## LLM Interpretation

Mock review for a binary DGP contract. Findings are organized by the mock LLM, while validation and statistical checks are deterministic.

### Estimand clarity

- Deterministic check: {'name': 'marginal_risk_difference', 'contrast': 'E[Y(1) - Y(0)]', 'primary': 'risk_difference'}
- LLM interpretation: The contract names an estimand before simulation; deterministic truth engines compute the target.

### Truth engine availability

- Deterministic check: oracle Monte Carlo over counterfactual probabilities
- LLM interpretation: The LLM does not compute truth; it only explains which deterministic truth engine applies.

### Uncertainty reporting

- Deterministic check: binary risk estimators expose lightweight implemented intervals where available
- LLM interpretation: Unsupported SE/CI/coverage rows should remain blank rather than be narrated as valid.
- Unresolved decision: Decide whether additional interval estimators are needed for the final study.

## Safeguard

Do not treat this review as statistical evidence. Run the deterministic DGPForge pipeline for truth, Monte Carlo summaries, diagnostics, and report artifacts.
