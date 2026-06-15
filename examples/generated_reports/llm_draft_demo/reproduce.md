# Reproduce This Report

From this output directory, rerun the deterministic report pipeline with:

```bash
dgpforge run --config contract.yaml --out .
```

Original command recorded when this report was generated:

```bash
dgpforge draft --prompt "Create a simulation with binary treatment, continuous outcome, moderate confounding, heterogeneous treatment effect by X1, 500 units, 30 replications, and compare naive, IPW, and AIPW." --provider mock --out examples/generated_reports/llm_draft_demo --run
```

The command above regenerates the known-truth Monte Carlo report artifacts from the saved contract. LLM-assisted extraction, drafting, and review logs are preserved separately when those modes are used.
