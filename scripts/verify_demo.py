"""Write or verify the curated generated-report manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
GENERATED_REPORTS_DIR = ROOT / "examples" / "generated_reports"
MANIFEST_NAME = "manifest.json"


class ManifestError(RuntimeError):
    """Raised when generated-report artifacts do not match the manifest."""


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _manifest_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if b"\0" in data:
        return data
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(_manifest_bytes(path))
    return digest.hexdigest()


def _file_size(path: Path) -> int:
    return len(_manifest_bytes(path))


def _iter_manifest_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and _relative_path(path, root) != MANIFEST_NAME
    )


def build_manifest(root: Path = GENERATED_REPORTS_DIR) -> dict[str, list[dict[str, object]]]:
    """Build deterministic metadata for all curated generated-report files."""
    root = Path(root)
    files = [
        {
            "path": _relative_path(path, root),
            "sha256": _file_sha256(path),
            "size_bytes": _file_size(path),
        }
        for path in _iter_manifest_files(root)
    ]
    return {"files": files}


def write_manifest(root: Path = GENERATED_REPORTS_DIR) -> Path:
    """Write manifest.json for the generated-report directory."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / MANIFEST_NAME
    manifest = build_manifest(root)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest_path


def check_manifest(root: Path = GENERATED_REPORTS_DIR) -> None:
    """Verify generated-report files against manifest.json."""
    root = Path(root)
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.exists():
        raise ManifestError(f"missing manifest: {manifest_path}")

    expected = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_files = expected.get("files", [])
    if not isinstance(expected_files, list):
        raise ManifestError("manifest field 'files' must be a list")

    expected_by_path = {str(item["path"]): item for item in expected_files}
    errors: list[str] = []
    for relative, item in expected_by_path.items():
        path = root / relative
        if not path.exists():
            errors.append(f"missing file: {relative}")
            continue
        actual_size = _file_size(path)
        actual_sha = _file_sha256(path)
        if actual_size != item.get("size_bytes"):
            errors.append(
                f"size mismatch for {relative}: expected {item.get('size_bytes')}, got {actual_size}"
            )
        if actual_sha != item.get("sha256"):
            errors.append(f"sha256 mismatch for {relative}")

    actual_paths = {_relative_path(path, root) for path in _iter_manifest_files(root)}
    extra_paths = sorted(actual_paths - set(expected_by_path))
    for relative in extra_paths:
        print(f"warning: extra generated-report file not in manifest: {relative}", file=sys.stderr)

    if errors:
        raise ManifestError("; ".join(errors))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--write", action="store_true", help="write examples/generated_reports/manifest.json"
    )
    mode.add_argument("--check", action="store_true", help="verify files against manifest.json")
    parser.add_argument(
        "--root",
        default=GENERATED_REPORTS_DIR,
        type=Path,
        help="generated-report root to inspect",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.write:
            manifest_path = write_manifest(args.root)
            print(f"Wrote {manifest_path}")
        else:
            check_manifest(args.root)
            print("Demo manifest check passed")
    except ManifestError as exc:
        print(f"Demo manifest check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
