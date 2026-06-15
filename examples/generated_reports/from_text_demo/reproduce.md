# Reproduce This Report

From this output directory, rerun the deterministic report pipeline with:

```bash
dgpforge run --config contract.yaml --out .
```

Original command recorded when this report was generated:

```bash
dgpforge from-text --input examples/paper_excerpt_causal_ate.txt --out examples/generated_reports/from_text_demo
```

The command above regenerates the known-truth Monte Carlo report artifacts from the saved contract. LLM-assisted extraction, drafting, and review logs are preserved separately when those modes are used.
