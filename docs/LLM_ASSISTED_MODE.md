# LLM-Assisted Mode

DGPForge works fully without an LLM. The deterministic engine accepts YAML causal DGP contracts, validates them, computes known causal truth, simulates data, benchmarks estimators, runs diagnostics, and writes reports.

The optional LLM-assisted layer helps prepare or review causal DGP contracts. It does not infer causal truth from observed data, perform causal discovery, or generate statistical evidence.

## Supported Assisted Commands

```bash
dgpforge draft --prompt "Create a simulation with binary treatment, continuous outcome, moderate confounding, 500 units, 100 replications, and compare naive, IPW, and AIPW." --provider mock --out outputs/draft --run
dgpforge from-paper --input examples/paper_excerpt_causal_ate.txt --provider mock --out outputs/paper --run
dgpforge review --config examples/causal_binary_outcome.yaml --provider mock --out outputs/review
```

- `draft` converts a natural-language prompt into a draft causal DGP contract.
- `from-paper` extracts a draft causal DGP contract from a text excerpt. It is not a general paper reproduction system and does not parse PDFs.
- `review` runs deterministic checks on an existing YAML contract, then uses the provider only to organize review findings.

## Validation Gate

Provider outputs are structured dictionaries, not trusted free-form YAML. DGPForge validates the structured response and then validates `draft_dgp.yaml` with the deterministic `DGPContract` schema.

If validation fails, DGPForge writes `validation_errors.md` and does not run simulation. If validation passes and `--run` is set, the deterministic engine produces the report.

## Artifacts

Draft and paper workflows write:

- `draft_dgp.yaml`
- `assumptions_log.md`
- `unresolved_questions.md`
- `validation_report.md`
- `agent_run_summary.md`
- `source_trace.md` for prompt mode or `extraction_trace.md` for paper mode
- `report.html` only when `--run` is requested and validation passes

Review mode writes:

- `deterministic_checks.json`
- `deterministic_checks.md`
- `review_report.md`
- `suggested_questions.md`

## Safeguards

- The LLM may draft config fields, extract simulation settings, review a config, and summarize caveats.
- The LLM may not invent causal truth, infer causal truth from observed data, perform causal discovery, override deterministic calculations, silently fill assumptions, report unsupported uncertainty, or claim estimator validity without deterministic evidence.
- All causal estimands and benchmark results come from deterministic modules.
- All LLM-filled assumptions are logged.
- Provider keys are optional and never needed for tests or demos.
- The bundled `mock` provider is deterministic and reproducible.
- External provider adapters, if added later, should remain isolated optional dependencies.
