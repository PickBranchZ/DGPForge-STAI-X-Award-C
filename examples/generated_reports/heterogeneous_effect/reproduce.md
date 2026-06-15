# Reproduce This Report

From this output directory, rerun the deterministic report pipeline with:

```bash
dgpforge run --config contract.yaml --out .
```

Original command recorded when this report was generated:

```bash
dgpforge run --config examples/causal_ate_heterogeneous_effect.yaml --out examples/generated_reports/heterogeneous_effect
```

The command above regenerates the known-truth Monte Carlo report artifacts from the saved contract. LLM-assisted extraction, drafting, and review logs are preserved separately when those modes are used.
