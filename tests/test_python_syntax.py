"""Fail CI if any project Python file cannot be parsed."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".venv", ".git", "__pycache__", ".hypothesis", ".pytest_cache"}


def _python_files():
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        yield path


def test_all_project_python_files_parse():
    errors = []
    files = list(_python_files())
    assert files, "expected project Python files"
    for path in files:
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")
    assert not errors, "syntax errors:\n" + "\n".join(errors)
