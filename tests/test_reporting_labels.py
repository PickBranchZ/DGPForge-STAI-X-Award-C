from dgpforge.reporting.labels import title_case_name


def test_title_case_name_preserves_statistical_acronyms() -> None:
    assert title_case_name("llm_draft_heterogeneous_ate") == "LLM Draft Heterogeneous ATE"
    assert title_case_name("paper_llm_causal_ate_demo") == "Paper LLM Causal ATE Demo"
    assert title_case_name("clustered_icc") == "Clustered ICC"
    assert title_case_name("dgp_yaml_html_ci_rmse_mcse") == "DGP YAML HTML CI RMSE MCSE"
