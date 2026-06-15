from __future__ import annotations

import pytest

from scripts.verify_demo import ManifestError, check_manifest, write_manifest


def test_demo_manifest_write_and_check_detects_mutation(workspace_tmp_path) -> None:
    (workspace_tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    nested = workspace_tmp_path / "nested"
    nested.mkdir()
    (nested / "b.txt").write_text("beta\n", encoding="utf-8")

    manifest_path = write_manifest(workspace_tmp_path)

    assert manifest_path.exists()
    check_manifest(workspace_tmp_path)

    (workspace_tmp_path / "a.txt").write_text("changed\n", encoding="utf-8")

    with pytest.raises(ManifestError, match="sha256 mismatch"):
        check_manifest(workspace_tmp_path)


def test_demo_manifest_normalizes_text_line_endings(workspace_tmp_path) -> None:
    text_path = workspace_tmp_path / "report.html"
    text_path.write_bytes(b"<html>\n<body>ok</body>\n</html>\n")

    write_manifest(workspace_tmp_path)
    text_path.write_bytes(b"<html>\r\n<body>ok</body>\r\n</html>\r\n")

    check_manifest(workspace_tmp_path)

    text_path.write_bytes(b"<html>\r\n<body>changed</body>\r\n</html>\r\n")
    with pytest.raises(ManifestError, match="size mismatch|sha256 mismatch"):
        check_manifest(workspace_tmp_path)
