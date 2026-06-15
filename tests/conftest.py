from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def workspace_tmp_path(request: pytest.FixtureRequest) -> Path:
    """Workspace-local temp directory for tests that write generated artifacts."""
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.name)
    root = Path.cwd() / "test_tmp" / safe_name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        if root.exists():
            shutil.rmtree(root)
