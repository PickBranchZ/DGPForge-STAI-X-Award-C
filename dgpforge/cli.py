"""Command line interface for DGPForge."""

from __future__ import annotations

import argparse
from pathlib import Path

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


def _run_config(config: str | Path, out: str | Path) -> Path:
    contract = load_contract(config)
    result = run_monte_carlo(contract)
    command = f"dgpforge run --config {config} --out {out}"
    return generate_report(
        contract,
        result,
        out_dir=out,
        command=command,
        contract_source_path=config,
    )


def _run_from_text(input_path: str | Path, out: str | Path) -> Path:
    contract, assumptions_path = parse_paper_excerpt(input_path, out)
    result = run_monte_carlo(contract)
    command = f"dgpforge from-text --input {input_path} --out {out}"
    return generate_report(
        contract,
        result,
        out_dir=out,
        command=command,
        assumptions_log_path=assumptions_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dgpforge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("--out", required=True)

    text_parser = subparsers.add_parser("from-text")
    text_parser.add_argument("--input", required=True)
    text_parser.add_argument("--out", required=True)

    grid_parser = subparsers.add_parser("grid")
    grid_parser.add_argument("--config", required=True)
    grid_parser.add_argument("--out", required=True)

    sensitivity_parser = subparsers.add_parser("sensitivity")
    sensitivity_parser.add_argument("--config", required=True)
    sensitivity_parser.add_argument("--out", required=True)

    calibrate_parser = subparsers.add_parser("calibrate")
    calibrate_parser.add_argument("--config", required=True)
    calibrate_parser.add_argument("--out", required=True)

    draft_parser = subparsers.add_parser("draft")
    draft_parser.add_argument("--prompt", required=True)
    draft_parser.add_argument("--out", required=True)
    draft_parser.add_argument("--provider", default="mock")
    draft_parser.add_argument("--run", action="store_true")

    paper_parser = subparsers.add_parser("from-paper")
    paper_parser.add_argument("--input", required=True)
    paper_parser.add_argument("--out", required=True)
    paper_parser.add_argument("--provider", default="mock")
    paper_parser.add_argument("--run", action="store_true")

    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("--config", required=True)
    review_parser.add_argument("--out", required=True)
    review_parser.add_argument("--provider", default="mock")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        report_path = _run_config(args.config, args.out)
    elif args.command == "from-text":
        report_path = _run_from_text(args.input, args.out)
    elif args.command == "grid":
        report_path = run_scenario_grid(args.config, args.out)
    elif args.command == "sensitivity":
        report_path = run_sensitivity_grid(args.config, args.out)
    elif args.command == "calibrate":
        report_path = run_calibration(args.config, args.out)
    elif args.command == "draft":
        command = (
            f"dgpforge draft --prompt {args.prompt!r} --provider {args.provider} "
            f"--out {args.out}{' --run' if args.run else ''}"
        )
        result = run_draft_workflow(
            args.prompt,
            args.out,
            provider_name=args.provider,
            run=args.run,
            command=command,
        )
        report_path = result.report_path or result.validation_report_path
    elif args.command == "from-paper":
        command = (
            f"dgpforge from-paper --input {args.input} --provider {args.provider} "
            f"--out {args.out}{' --run' if args.run else ''}"
        )
        result = run_from_paper_workflow(
            args.input,
            args.out,
            provider_name=args.provider,
            run=args.run,
            command=command,
        )
        report_path = result.report_path or result.validation_report_path
    else:
        report_path = run_review_workflow(args.config, args.out, provider_name=args.provider)
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
