from __future__ import annotations

from pathlib import Path

import pytest

from scripts.build_demo import NARRATIVE, render_hero_gallery


HERO_TITLES = [
    "LLM draft \u2192 causal DGP contract",
    "Observed confounding / AIPW recovery",
    "Count/rate causal estimands",
    "Missingness as causal-data complication",
]


def _hero_demo(root: Path, key: str, title: str) -> dict[str, object]:
    out_dir = root / key
    out_dir.mkdir(parents=True)
    report_path = out_dir / "report.html"
    artifact_path = out_dir / "artifact.csv"
    report_path.write_text("<html>ok</html>", encoding="utf-8")
    artifact_path.write_text("value\n1\n", encoding="utf-8")
    return {
        "key": key,
        "title": title,
        "description": f"{title} description",
        "primary_report": report_path,
        "artifact_links": [("Artifact", artifact_path)],
    }


def test_hero_gallery_renders_four_cards_in_required_order(workspace_tmp_path: Path) -> None:
    demos = [
        _hero_demo(workspace_tmp_path, f"demo_{idx}", title)
        for idx, title in enumerate(HERO_TITLES)
    ]

    html = render_hero_gallery(demos, workspace_tmp_path)

    assert html.count('class="hero-card"') == 4
    assert [html.index(title) for title in HERO_TITLES] == sorted(
        html.index(title) for title in HERO_TITLES
    )
    assert 'class="card"' not in html


def test_hero_gallery_missing_required_report_fails_clearly(
    workspace_tmp_path: Path,
) -> None:
    demos = [_hero_demo(workspace_tmp_path, "missing", HERO_TITLES[0])]
    Path(demos[0]["primary_report"]).unlink()

    with pytest.raises(FileNotFoundError, match="Missing hero demo artifact"):
        render_hero_gallery(demos, workspace_tmp_path)


def test_generated_gallery_artifact_keeps_hero_contract() -> None:
    text = Path("examples/generated_reports/index.html").read_text(encoding="utf-8")
    hero_section = text.split('<div class="hero-gallery">', maxsplit=1)[1].split(
        "</div>", maxsplit=1
    )[0]

    assert text.count('class="hero-card"') == 4
    assert [text.index(title) for title in HERO_TITLES] == sorted(
        text.index(title) for title in HERO_TITLES
    )
    assert 'class="card"' not in hero_section
    assert "<h3>Observed Confounding</h3>" not in hero_section
    assert "<h3>Count/Rate Outcome</h3>" not in hero_section
    assert "<h3>Missing Data Mechanisms</h3>" not in hero_section
    assert "<h3>Clustered ICC</h3>" in text
    assert '<h2 id="more-examples">More examples</h2>' in text
    assert 'src="assets/report_preview.png"' in text
    assert 'href="assets/architecture.svg">Architecture diagram</a>' in text
    assert 'href="evaluation.html">Evaluation notes</a>' in text
    assert Path("examples/generated_reports/evaluation.html").exists()


def test_evaluation_notes_have_required_scope_sections() -> None:
    text = Path("EVALUATION.md").read_text(encoding="utf-8")

    assert text.startswith("# Evaluation\n\n" + NARRATIVE)
    assert "## What the automated tests cover" in text
    assert "## What the benchmark verifies" in text
    assert "## What the hero reports demonstrate" in text
    assert "## What this does not prove" in text
    assert "## How to reproduce" in text
    assert "python scripts/verify_demo.py --check" in text
    assert 80 <= len(text.splitlines()) <= 140
