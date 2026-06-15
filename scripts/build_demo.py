"""Regenerate the static DGPForge demo gallery and final report artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dgpforge.curated_parser import parse_paper_excerpt
from dgpforge.calibration import run_calibration
from dgpforge.contracts import load_contract
from dgpforge.grid import run_scenario_grid
from dgpforge.llm.config_reviewer import run_review_workflow
from dgpforge.llm.contract_drafter import run_draft_workflow
from dgpforge.llm.paper_extractor import run_from_paper_workflow
from dgpforge.monte_carlo import run_monte_carlo
from dgpforge.report import generate_report
from dgpforge.sensitivity import run_sensitivity_grid
from scripts.verify_demo import write_manifest


@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    description: str
    expected: str
    report_dir: Path
    config: Path | None = None
    grid_config: Path | None = None
    sensitivity_config: Path | None = None
    calibration_config: Path | None = None
    text_input: Path | None = None


SCENARIOS = [
    Scenario(
        key="randomized",
        title="Randomized Treatment",
        description="Treatment is independent of covariates.",
        expected="Naive difference should be approximately unbiased.",
        config=ROOT / "examples" / "causal_ate_randomized.yaml",
        report_dir=ROOT / "examples" / "generated_reports" / "randomized",
    ),
    Scenario(
        key="observed_confounding",
        title="Observed Confounding",
        description="Treatment depends on prognostic covariates X1 and X2.",
        expected="Naive estimator is biased; adjusted/AIPW should be closer to truth.",
        config=ROOT / "examples" / "causal_ate_observed_confounding.yaml",
        report_dir=ROOT / "examples" / "generated_reports" / "observed_confounding",
    ),
    Scenario(
        key="weak_overlap",
        title="Weak Overlap",
        description="Treatment assignment is strongly separated by covariates.",
        expected="Positivity warning should trigger; IPW may become unstable.",
        config=ROOT / "examples" / "causal_ate_weak_overlap.yaml",
        report_dir=ROOT / "examples" / "generated_reports" / "weak_overlap",
    ),
    Scenario(
        key="heterogeneous_effect",
        title="Heterogeneous Effect",
        description="Treatment effect varies with binary modifier X2.",
        expected="True marginal ATE averages the configured individual effects.",
        config=ROOT / "examples" / "causal_ate_heterogeneous_effect.yaml",
        report_dir=ROOT / "examples" / "generated_reports" / "heterogeneous_effect",
    ),
    Scenario(
        key="double_robustness",
        title="Double Robustness",
        description="AIPW variants deliberately misspecify one or both nuisance models.",
        expected="One-correct variants should be closer to truth than the double-misspecified variant in this seeded DGP.",
        config=ROOT / "examples" / "causal_ate_double_robustness.yaml",
        report_dir=ROOT / "examples" / "generated_reports" / "double_robustness",
    ),
    Scenario(
        key="scenario_grid",
        title="Scenario Grid",
        description="One base contract expands across sample sizes, confounding strengths, and effect patterns.",
        expected="Grid summary compares finite Monte Carlo evidence across DGP cells.",
        grid_config=ROOT / "examples" / "scenario_grid_causal_ate.yaml",
        report_dir=ROOT / "examples" / "generated_reports" / "scenario_grid",
    ),
    Scenario(
        key="binary_outcome",
        title="Binary Outcome",
        description="Logistic binary-outcome DGP with marginal risk-difference benchmarking.",
        expected="Reports marginal risks, risk difference, risk ratio, and the conditional-vs-marginal distinction.",
        config=ROOT / "examples" / "causal_binary_outcome.yaml",
        report_dir=ROOT / "examples" / "generated_reports" / "binary_outcome",
    ),
    Scenario(
        key="unmeasured_confounding_sensitivity",
        title="Unmeasured Confounding Sensitivity",
        description="Latent U affects treatment and outcome but is hidden from observed estimators.",
        expected="Bias surfaces show how hidden-confounding strength changes estimator bias under known truth.",
        sensitivity_config=ROOT / "examples" / "unmeasured_confounding_sensitivity.yaml",
        report_dir=ROOT / "examples" / "generated_reports" / "unmeasured_confounding_sensitivity",
    ),
    Scenario(
        key="count_rate_outcome",
        title="Count/Rate Outcome",
        description="Public-health-style event counts with exposure denominators.",
        expected="Simulates public-health event counts with exposure denominators and known rate estimands.",
        config=ROOT / "examples" / "causal_count_rate_outcome.yaml",
        report_dir=ROOT / "examples" / "generated_reports" / "count_rate_outcome",
    ),
    Scenario(
        key="missing_data",
        title="Missing Data Mechanisms",
        description="MAR outcome missingness with full-data truth preserved.",
        expected="Compares complete-case and missingness-IPW analyses under an explicit observed-data mechanism.",
        config=ROOT / "examples" / "missing_data_mechanisms.yaml",
        report_dir=ROOT / "examples" / "generated_reports" / "missing_data",
    ),
    Scenario(
        key="clustered_icc",
        title="Clustered ICC",
        description="Continuous outcomes nested in clusters with a configured ICC.",
        expected="Shows why cluster-aware SEs matter for coverage when observations are clustered.",
        config=ROOT / "examples" / "clustered_ate_icc.yaml",
        report_dir=ROOT / "examples" / "generated_reports" / "clustered_icc",
    ),
    Scenario(
        key="calibration_demo",
        title="DGP Calibration",
        description="Design targets are converted into calibrated DGP parameters.",
        expected="Reports requested vs achieved target moments under the configured synthetic DGP.",
        calibration_config=ROOT / "examples" / "calibration_targets.yaml",
        report_dir=ROOT / "examples" / "generated_reports" / "calibration_demo",
    ),
    Scenario(
        key="from_text_demo",
        title="From-Text Demo",
        description="Curated simulation-section extraction creates a contract and assumptions log.",
        expected="Parser demonstrates provenance; it is not general paper reproduction.",
        text_input=ROOT / "examples" / "paper_excerpt_causal_ate.txt",
        report_dir=ROOT / "examples" / "generated_reports" / "from_text_demo",
    ),
]


NARRATIVE = "Known-truth causal DGP simulation for estimator stress-testing."
HERO_SECOND_SENTENCE = (
    "Specify a causal DGP, generate potential outcomes, compute the known causal estimand, "
    "and benchmark estimators against that truth."
)
EXPECTED_PAGES_URL = "https://pickbranchz.github.io/DGPForge-STAI-X-Award-C/"

HERO_DEMOS = [
    {
        "key": "llm_draft_demo",
        "title": "LLM draft \u2192 causal DGP contract",
        "description": (
            "Natural-language study design becomes a validated causal DGP contract, "
            "assumptions log, known-truth run, and deterministic report."
        ),
        "primary_report": ROOT
        / "examples"
        / "generated_reports"
        / "llm_draft_demo"
        / "report.html",
        "artifact_links": [
            (
                "Draft YAML",
                ROOT / "examples" / "generated_reports" / "llm_draft_demo" / "draft_dgp.yaml",
            ),
            (
                "Validation",
                ROOT / "examples" / "generated_reports" / "llm_draft_demo" / "validation_report.md",
            ),
            (
                "Assumptions",
                ROOT / "examples" / "generated_reports" / "llm_draft_demo" / "assumptions_log.md",
            ),
        ],
    },
    {
        "key": "observed_confounding",
        "title": "Observed confounding / AIPW recovery",
        "description": (
            "Treatment depends on prognostic covariates, so naive estimation is biased "
            "while adjusted and AIPW estimators move toward the marginal ATE."
        ),
        "primary_report": ROOT
        / "examples"
        / "generated_reports"
        / "observed_confounding"
        / "report.html",
        "artifact_links": [
            (
                "Estimator CSV",
                ROOT
                / "examples"
                / "generated_reports"
                / "observed_confounding"
                / "estimator_summary.csv",
            ),
            (
                "Reproduce",
                ROOT / "examples" / "generated_reports" / "observed_confounding" / "reproduce.md",
            ),
        ],
    },
    {
        "key": "count_rate_outcome",
        "title": "Count/rate causal estimands",
        "description": (
            "Event counts with exposure denominators show marginal rate differences, "
            "rate ratios, and honest uncertainty availability."
        ),
        "primary_report": ROOT
        / "examples"
        / "generated_reports"
        / "count_rate_outcome"
        / "report.html",
        "artifact_links": [
            (
                "Estimator CSV",
                ROOT
                / "examples"
                / "generated_reports"
                / "count_rate_outcome"
                / "estimator_summary.csv",
            ),
            (
                "Diagnostics",
                ROOT / "examples" / "generated_reports" / "count_rate_outcome" / "diagnostics.csv",
            ),
        ],
    },
    {
        "key": "missing_data",
        "title": "Missingness as causal-data complication",
        "description": (
            "Configured MCAR, MAR, or MNAR mechanisms preserve known full-data "
            "truth while comparing complete-case and missingness-IPW behavior."
        ),
        "primary_report": ROOT / "examples" / "generated_reports" / "missing_data" / "report.html",
        "artifact_links": [
            (
                "Estimator CSV",
                ROOT / "examples" / "generated_reports" / "missing_data" / "estimator_summary.csv",
            ),
            (
                "Diagnostics",
                ROOT / "examples" / "generated_reports" / "missing_data" / "diagnostics.csv",
            ),
        ],
    },
]


def _rel(path: Path, start: Path) -> str:
    return os.path.relpath(path, start).replace("\\", "/")


def _html_block(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def _run_scenario(scenario: Scenario) -> dict[str, object]:
    if scenario.grid_config is not None:
        command = f"dgpforge grid --config {_rel(scenario.grid_config, ROOT)} --out {_rel(scenario.report_dir, ROOT)}"
        report_path = run_scenario_grid(
            scenario.grid_config,
            scenario.report_dir,
            command=command,
        )
        summary = pd.read_csv(scenario.report_dir / "scenario_summary.csv")
        positivity = "Warning" if bool(summary["positivity_warning"].any()) else "Pass"
        return {
            "scenario": scenario,
            "truth": None,
            "truth_display": "varies by cell",
            "positivity": positivity,
            "report_path": report_path,
        }

    if scenario.sensitivity_config is not None:
        command = f"dgpforge sensitivity --config {_rel(scenario.sensitivity_config, ROOT)} --out {_rel(scenario.report_dir, ROOT)}"
        report_path = run_sensitivity_grid(
            scenario.sensitivity_config,
            scenario.report_dir,
            command=command,
        )
        summary = pd.read_csv(scenario.report_dir / "sensitivity_summary.csv")
        positivity = "Warning" if bool(summary["positivity_warning"].any()) else "Pass"
        return {
            "scenario": scenario,
            "truth": None,
            "truth_display": "varies by U grid",
            "positivity": positivity,
            "report_path": report_path,
        }

    if scenario.calibration_config is not None:
        command = f"dgpforge calibrate --config {_rel(scenario.calibration_config, ROOT)} --out {_rel(scenario.report_dir, ROOT)}"
        report_path = run_calibration(
            scenario.calibration_config,
            scenario.report_dir,
            command=command,
        )
        summary = pd.read_csv(scenario.report_dir / "calibration_summary.csv")
        passed = bool(summary[summary["status"] == "calibrated"]["passed"].all())
        return {
            "scenario": scenario,
            "truth": None,
            "truth_display": "target checks",
            "positivity": "Pass" if passed else "Review",
            "report_path": report_path,
        }

    if scenario.config is not None:
        contract = load_contract(scenario.config)
        command = f"dgpforge run --config {_rel(scenario.config, ROOT)} --out {_rel(scenario.report_dir, ROOT)}"
        assumptions_path = None
    else:
        contract, assumptions_path = parse_paper_excerpt(scenario.text_input, scenario.report_dir)
        command = f"dgpforge from-text --input {_rel(scenario.text_input, ROOT)} --out {_rel(scenario.report_dir, ROOT)}"

    result = run_monte_carlo(contract)
    report_path = generate_report(
        contract,
        result,
        out_dir=scenario.report_dir,
        command=command,
        assumptions_log_path=assumptions_path,
        contract_source_path=scenario.config,
    )
    positivity = "Warning" if bool(result.diagnostics["positivity_warning"].any()) else "Pass"
    return {
        "scenario": scenario,
        "contract": contract,
        "truth": result.truth,
        "truth_display": f"{result.truth:.3f}",
        "positivity": positivity,
        "report_path": report_path,
    }


def _as_path(value: object) -> Path:
    if isinstance(value, Path):
        return value
    return Path(str(value))


def validate_hero_demos(hero_demos: list[dict[str, object]]) -> None:
    missing = []
    for demo in hero_demos:
        title = str(demo["title"])
        primary_report = _as_path(demo["primary_report"])
        if not primary_report.exists():
            missing.append(f"{title} primary report: {primary_report}")
        for label, artifact in demo.get("artifact_links", []):
            artifact_path = _as_path(artifact)
            if not artifact_path.exists():
                missing.append(f"{title} {label}: {artifact_path}")
    if missing:
        raise FileNotFoundError(
            "Missing hero demo artifact(s): " + "; ".join(str(item) for item in missing)
        )


def _artifact_links(artifact_links: list[tuple[str, Path]], gallery_dir: Path) -> str:
    if not artifact_links:
        return ""
    items = []
    for label, artifact in artifact_links:
        href = _rel(_as_path(artifact), gallery_dir)
        items.append(f'<li><a href="{escape(href)}">{escape(label)}</a></li>')
    return '<ul class="artifact-links">' + "\n".join(items) + "</ul>"


def _hero_card(demo: dict[str, object], gallery_dir: Path) -> str:
    report_href = _rel(_as_path(demo["primary_report"]), gallery_dir)
    artifact_links = _artifact_links(demo.get("artifact_links", []), gallery_dir)
    return _html_block(
        f"""
      <article class="hero-card">
        <p class="kicker">Hero demo</p>
        <h3>{escape(str(demo["title"]))}</h3>
        <p>{escape(str(demo["description"]))}</p>
        <a class="primary-link" href="{escape(report_href)}">Open report</a>
        {artifact_links}
      </article>
    """
    )


def render_hero_gallery(hero_demos: list[dict[str, object]], gallery_dir: Path) -> str:
    validate_hero_demos(hero_demos)
    return "\n".join(_hero_card(demo, gallery_dir) for demo in hero_demos)


def _card(row: dict[str, object], gallery_dir: Path) -> str:
    scenario: Scenario = row["scenario"]
    report_href = _rel(row["report_path"], gallery_dir)
    tag_class = "ok" if row["positivity"] == "Pass" else "warn"
    return _html_block(
        f"""
      <article class="card">
        <div class="scenario-tag {tag_class}">{escape(row['positivity'])}</div>
        <h3>{escape(scenario.title)}</h3>
        <p>{escape(scenario.description)}</p>
        <p class="expected">{escape(scenario.expected)}</p>
        <a href="{escape(report_href)}">Open report</a>
      </article>
    """
    )


def _comparison_table(rows: list[dict[str, object]], gallery_dir: Path) -> str:
    body = []
    for row in rows:
        scenario: Scenario = row["scenario"]
        report_href = _rel(row["report_path"], gallery_dir)
        body.append(
            _html_block(
                f"""
          <tr>
            <td>{escape(scenario.title)}</td>
            <td>{escape(str(row['truth_display']))}</td>
            <td>{escape(str(row['positivity']))}</td>
            <td>{escape(scenario.expected)}</td>
            <td><a href="{escape(report_href)}">report.html</a></td>
          </tr>
          """
            )
        )
    return "\n".join(body)


def _build_llm_demos() -> list[dict[str, object]]:
    draft_out = ROOT / "examples" / "generated_reports" / "llm_draft_demo"
    paper_out = ROOT / "examples" / "generated_reports" / "paper_llm_demo"
    review_out = ROOT / "examples" / "generated_reports" / "config_review_demo"

    draft_prompt = (
        "Create a simulation with binary treatment, continuous outcome, moderate confounding, "
        "heterogeneous treatment effect by X1, 500 units, 30 replications, and compare naive, IPW, and AIPW."
    )
    draft_command = (
        'dgpforge draft --prompt "Create a simulation with binary treatment, continuous outcome, '
        "moderate confounding, heterogeneous treatment effect by X1, 500 units, 30 replications, "
        'and compare naive, IPW, and AIPW." --provider mock --out examples/generated_reports/llm_draft_demo --run'
    )
    draft_result = run_draft_workflow(
        draft_prompt,
        draft_out,
        provider_name="mock",
        run=True,
        command=draft_command,
    )

    paper_command = (
        "dgpforge from-paper --input examples/paper_excerpt_causal_ate.txt --provider mock "
        "--out examples/generated_reports/paper_llm_demo --run"
    )
    paper_result = run_from_paper_workflow(
        ROOT / "examples" / "paper_excerpt_causal_ate.txt",
        paper_out,
        provider_name="mock",
        run=True,
        command=paper_command,
    )

    review_path = run_review_workflow(
        ROOT / "examples" / "causal_binary_outcome.yaml",
        review_out,
        provider_name="mock",
    )

    return [
        {
            "key": "llm_draft_demo",
            "title": "Natural language to DGP contract",
            "description": "Mock LLM drafts a validated causal DGP YAML, then Module A generates the deterministic report.",
            "status": "Validated" if draft_result.validation_passed else "Review",
            "artifact_path": draft_result.report_path or draft_result.validation_report_path,
            "expected": "draft_dgp.yaml, assumptions_log.md, validation_report.md, report.html, and agent_run_summary.md",
        },
        {
            "key": "paper_llm_demo",
            "title": "Paper excerpt to DGP contract",
            "description": "Mock paper extraction writes a draft contract, assumptions log, extraction trace, and deterministic report.",
            "status": "Validated" if paper_result.validation_passed else "Review",
            "artifact_path": paper_result.report_path or paper_result.validation_report_path,
            "expected": "draft_dgp.yaml, extraction_trace.md, unresolved_questions.md, validation_report.md, and report.html",
        },
        {
            "key": "config_review_demo",
            "title": "Config review",
            "description": "Existing YAML receives deterministic checks plus mock LLM organization of review findings.",
            "status": "Checks",
            "artifact_path": review_path,
            "expected": "review_report.md, deterministic_checks.json, deterministic_checks.md, and suggested_questions.md",
        },
    ]


def _llm_card(row: dict[str, object], gallery_dir: Path) -> str:
    artifact_href = _rel(row["artifact_path"], gallery_dir)
    tag_class = "ok" if row["status"] in {"Validated", "Checks"} else "warn"
    link_label = "Open artifact"
    if str(row["artifact_path"]).endswith("report.html"):
        link_label = "Open report"
    return _html_block(
        f"""
      <article class="card">
        <div class="scenario-tag {tag_class}">{escape(str(row['status']))}</div>
        <h3>{escape(str(row['title']))}</h3>
        <p>{escape(str(row['description']))}</p>
        <p class="expected">{escape(str(row['expected']))}</p>
        <a href="{escape(artifact_href)}">{link_label}</a>
      </article>
    """
    )


def _render_markdown_html(markdown_text: str, title: str) -> str:
    lines = markdown_text.splitlines()
    body: list[str] = []
    paragraph: list[str] = []
    list_open = False
    code_open = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            body.append(f"<p>{escape(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            body.append("</ul>")
            list_open = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if code_open:
                body.append("<pre><code>" + escape("\n".join(code_lines)) + "</code></pre>")
                code_lines.clear()
                code_open = False
            else:
                flush_paragraph()
                close_list()
                code_open = True
            continue
        if code_open:
            code_lines.append(line)
            continue
        if not stripped:
            flush_paragraph()
            close_list()
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            close_list()
            body.append(f"<h1>{escape(stripped[2:])}</h1>")
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            close_list()
            body.append(f"<h2>{escape(stripped[3:])}</h2>")
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            if not list_open:
                body.append("<ul>")
                list_open = True
            body.append(f"<li>{escape(stripped[2:])}</li>")
            continue
        paragraph.append(stripped)

    flush_paragraph()
    close_list()
    if code_open:
        body.append("<pre><code>" + escape("\n".join(code_lines)) + "</code></pre>")

    content = "\n".join(body)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --ink: #172033;
      --muted: #5f6d82;
      --line: #d8deea;
      --panel: #f6f8fb;
      --accent: #22545f;
    }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #fff;
      line-height: 1.58;
    }}
    main {{
      width: min(860px, calc(100% - 32px));
      margin: 0 auto;
      padding: 44px 0 64px;
    }}
    nav {{
      margin-bottom: 24px;
    }}
    a {{
      color: var(--accent);
      font-weight: 700;
      text-decoration: none;
    }}
    h1 {{
      margin: 0 0 18px;
      font-size: 2.4rem;
      line-height: 1.1;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 34px 0 12px;
      font-size: 1.35rem;
      letter-spacing: 0;
    }}
    p, li {{
      color: #354258;
    }}
    ul {{
      padding-left: 1.35rem;
    }}
    pre {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: var(--panel);
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      font-size: 0.92rem;
    }}
  </style>
</head>
<body>
  <main>
    <nav><a href="index.html">Back to gallery</a></nav>
    {content}
  </main>
</body>
</html>
"""


def _write_evaluation_html(markdown_text: str, gallery_dir: Path) -> Path:
    evaluation_html = gallery_dir / "evaluation.html"
    evaluation_html.write_text(
        _render_markdown_html(markdown_text, "DGPForge Evaluation"),
        encoding="utf-8",
    )
    return evaluation_html


def _copy_gallery_assets(gallery_dir: Path) -> dict[str, Path]:
    asset_sources = {
        "report_preview": ROOT / "assets" / "report_preview.png",
        "architecture": ROOT / "assets" / "architecture.svg",
    }
    gallery_assets = gallery_dir / "assets"
    gallery_assets.mkdir(parents=True, exist_ok=True)
    copied = {}
    for key, source in asset_sources.items():
        if not source.exists():
            raise FileNotFoundError(f"Missing gallery asset: {source}")
        target = gallery_assets / source.name
        shutil.copyfile(source, target)
        copied[key] = target
    return copied


def _write_gallery_support_files(gallery_dir: Path) -> dict[str, Path]:
    evaluation_source = ROOT / "EVALUATION.md"
    if not evaluation_source.exists():
        raise FileNotFoundError(f"Missing evaluation notes: {evaluation_source}")
    evaluation_text = evaluation_source.read_text(encoding="utf-8")
    (gallery_dir / "EVALUATION.md").write_text(
        evaluation_text,
        encoding="utf-8",
    )
    _write_evaluation_html(evaluation_text, gallery_dir)
    benchmark_source = ROOT / "benchmark" / "results.md"
    if not benchmark_source.exists():
        raise FileNotFoundError(f"Missing benchmark summary: {benchmark_source}")
    benchmark_dir = gallery_dir / "benchmark"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    (benchmark_dir / "results.md").write_text(
        benchmark_source.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (gallery_dir / ".nojekyll").write_text("", encoding="utf-8")
    return _copy_gallery_assets(gallery_dir)


def write_gallery(rows: list[dict[str, object]], llm_rows: list[dict[str, object]]) -> Path:
    gallery_dir = ROOT / "examples" / "generated_reports"
    gallery_dir.mkdir(parents=True, exist_ok=True)
    static_assets = _write_gallery_support_files(gallery_dir)

    preview_path = static_assets["report_preview"]
    preview_html = ""
    if preview_path.exists():
        preview_html = f"""
        <figure class="report-preview">
          <img src="{escape(_rel(preview_path, gallery_dir))}" alt="DGPForge report preview">
          <figcaption>Preview of a generated DGPForge report.</figcaption>
        </figure>
        """

    hero_cards = render_hero_gallery(HERO_DEMOS, gallery_dir)
    hero_keys = {str(demo["key"]) for demo in HERO_DEMOS}
    more_rows = [row for row in rows if row["scenario"].key not in hero_keys]
    supporting_llm_rows = [row for row in llm_rows if str(row.get("key")) not in hero_keys]
    cards = "\n".join(_card(row, gallery_dir) for row in more_rows)
    llm_cards = "\n".join(_llm_card(row, gallery_dir) for row in supporting_llm_rows)
    table_rows = _comparison_table(rows, gallery_dir)

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DGPForge Award C Demo Gallery</title>
  <style>
    :root {{
      --ink: #172033;
      --muted: #5f6d82;
      --line: #d8deea;
      --panel: #f6f8fb;
      --accent: #2f6f7e;
      --accent-dark: #22545f;
      --ok: #256d49;
      --ok-bg: #eaf6ef;
      --warn: #954817;
      --warn-bg: #fff2e8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #ffffff;
      line-height: 1.5;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #f8fbfc 0%, #ffffff 100%);
    }}
    .hero, main {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
    }}
    .hero {{
      padding: 48px 0 32px;
    }}
    .eyebrow, .kicker {{
      margin: 0 0 10px;
      color: var(--accent-dark);
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0;
      font-size: 5.5rem;
      line-height: 1;
      letter-spacing: 0;
    }}
    .tagline {{
      margin: 18px 0 0;
      max-width: 820px;
      color: #354258;
      font-size: 1.22rem;
    }}
    .subline {{
      margin: 8px 0 0;
      max-width: 820px;
      color: var(--muted);
      font-size: 1rem;
    }}
    .utility-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 22px;
    }}
    main {{
      padding: 28px 0 48px;
    }}
    section {{
      margin-top: 34px;
    }}
    h2 {{
      margin: 0 0 8px;
      font-size: 1.35rem;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 0 0 10px;
      font-size: 1.05rem;
      letter-spacing: 0;
    }}
    .subtitle {{
      margin: 0 0 18px;
      color: var(--muted);
      max-width: 780px;
    }}
    .hero-gallery {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
    }}
    .gallery {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(245px, 1fr));
      gap: 16px;
    }}
    .hero-card, .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      background: #fff;
      min-width: 0;
    }}
    .hero-card {{
      background: var(--panel);
      display: flex;
      flex-direction: column;
      min-height: 285px;
    }}
    .hero-card p, .card p {{
      color: var(--muted);
      margin: 0 0 14px;
    }}
    .hero-card .primary-link {{
      margin-top: auto;
    }}
    .expected {{
      font-size: 0.92rem;
    }}
    .artifact-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      list-style: none;
      margin: 12px 0 0;
      padding: 0;
    }}
    .artifact-links a, .primary-link, .card a, .utility-links a {{
      color: var(--accent-dark);
      font-weight: 700;
      text-decoration: none;
    }}
    .artifact-links a {{
      font-size: 0.88rem;
    }}
    .scenario-tag {{
      display: inline-block;
      margin-bottom: 12px;
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 0.76rem;
      font-weight: 700;
    }}
    .scenario-tag.ok {{
      color: var(--ok);
      background: var(--ok-bg);
    }}
    .scenario-tag.warn {{
      color: var(--warn);
      background: var(--warn-bg);
    }}
    .report-preview {{
      margin: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #fff;
    }}
    .report-preview img {{
      width: 100%;
      display: block;
    }}
    .report-preview figcaption {{
      padding: 10px 14px;
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 760px;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: var(--panel);
    }}
    code {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 2px 6px;
      overflow-wrap: anywhere;
    }}
    @media (max-width: 980px) {{
      .hero-gallery {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 620px) {{
      .hero-gallery {{
        grid-template-columns: 1fr;
      }}
      .hero {{
        padding-top: 34px;
      }}
      .tagline {{
        font-size: 1.05rem;
      }}
      h1 {{
        font-size: 3.2rem;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="hero">
      <p class="eyebrow">DGPForge Award C demo gallery</p>
      <h1>DGPForge</h1>
      <p class="tagline">{escape(NARRATIVE)}</p>
      <p class="subline">{escape(HERO_SECOND_SENTENCE)}</p>
      <nav class="utility-links" aria-label="Gallery resources">
        <a href="evaluation.html">Evaluation notes</a>
        <a href="assets/architecture.svg">Architecture diagram</a>
        <a href="manifest.json">Manifest</a>
        <a href="benchmark/results.md">Benchmark summary</a>
      </nav>
    </div>
  </header>

  <main>
    <section aria-labelledby="hero-demos">
      <h2 id="hero-demos">Hero demos</h2>
      <p class="subtitle">Four compact entry points cover causal contract drafting, observed confounding, rate estimands, and observed-data complications.</p>
      <div class="hero-gallery">
        {hero_cards}
      </div>
    </section>

    <section aria-labelledby="more-examples">
      <h2 id="more-examples">More examples</h2>
      <p class="subtitle">Additional seeded causal DGP contracts exercise randomized treatment, weak overlap, heterogeneous effects, calibration, sensitivity, clustering, and double robustness.</p>
      <div class="gallery">
        {cards}
      </div>
    </section>

    <section aria-labelledby="llm-support">
      <h2 id="llm-support">LLM-assisted supporting artifacts</h2>
      <p class="subtitle">The optional LLM layer drafts or reviews causal DGP contracts, but deterministic validation gates execution and records assumptions.</p>
      <div class="gallery">
        {llm_cards}
      </div>
    </section>

    {preview_html}

    <section aria-labelledby="scenario-comparison">
      <h2 id="scenario-comparison">Scenario comparison</h2>
      <p class="subtitle">Pass or warning refers to positivity diagnostics only. Numeric results are finite Monte Carlo evidence under the seeded scenarios.</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Scenario</th><th>Known target</th><th>Positivity</th><th>Expected behavior</th><th>Report</th></tr>
          </thead>
          <tbody>
            {table_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="reproduce">
      <h2 id="reproduce">Reproduce this gallery</h2>
      <p class="subtitle">Run <code>python scripts/build_demo.py</code>, then <code>python scripts/verify_demo.py --check</code>. Public static gallery URL: <code>{EXPECTED_PAGES_URL}</code></p>
    </section>
  </main>
</body>
</html>
"""
    index_path = gallery_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path


def run_benchmark_results() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "benchmark" / "run_benchmark.py"), "--write-results"],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    rows = []
    for scenario in SCENARIOS:
        print(f"Building {scenario.key}...", flush=True)
        rows.append(_run_scenario(scenario))
    print("Building llm_assisted_demos...", flush=True)
    llm_rows = _build_llm_demos()
    run_benchmark_results()
    index_path = write_gallery(rows, llm_rows)
    print(f"Wrote {index_path.relative_to(ROOT).as_posix()}", flush=True)
    manifest_path = write_manifest(ROOT / "examples" / "generated_reports")
    print(f"Wrote {manifest_path.relative_to(ROOT).as_posix()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
