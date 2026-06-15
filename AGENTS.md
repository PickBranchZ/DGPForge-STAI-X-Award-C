# DGPForge Agent Manifest

## Modes

### Deterministic Causal DGP Module

- Input: YAML causal DGP contract.
- Actions: schema validation, truth calculation, simulation, estimator benchmarking, diagnostics, report generation.
- Outputs: `report.html`, CSV summaries, diagnostic plots, reproducibility command.
- LLM requirement: none.

### Optional LLM-Assisted Contract Module

- Input: natural-language prompt, paper-style text excerpt, or existing YAML causal DGP contract.
- Actions: draft config, extract simulation settings, review config, summarize caveats, log assumptions.
- Outputs: `draft_dgp.yaml`, `assumptions_log.md`, `unresolved_questions.md`, `validation_report.md`, `agent_run_summary.md`, extraction/source traces, review reports.
- LLM requirement: optional. The deterministic `mock` provider is used for tests and demos.

## Agent Loop

```text
Input -> Contract Draft -> Validation -> Execution -> Observation -> Report
```

Execution is skipped unless the draft passes deterministic `DGPContract` validation.

## LLM May

- Draft a DGP contract from a prompt.
- Extract structured simulation settings from a text excerpt.
- Review an existing YAML contract.
- Summarize assumptions, caveats, and unresolved user decisions.

## LLM May Not

- Invent statistical truth.
- Infer causal truth from observed data.
- Perform causal discovery or arbitrary DAG identification.
- Override deterministic truth engines, simulations, estimators, diagnostics, or reports.
- Silently fill missing assumptions.
- Report unsupported SE, CI, or coverage values.
- Claim an estimator is unbiased without deterministic Monte Carlo evidence under the configured DGP.

## Safeguards

- Provider outputs are parsed as structured responses before use.
- Drafted contracts are validated before execution.
- Assumptions and unresolved questions are written to disk.
- Statistical evidence, causal estimands, and benchmark results come only from deterministic DGPForge modules.
- The core package has no required external LLM dependency.
- No official STAI-X data, external real datasets, API keys, or secrets are included.
