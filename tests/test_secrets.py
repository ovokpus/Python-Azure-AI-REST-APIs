"""Guardrails so credentials do not land in the tree again."""

from __future__ import annotations

from pathlib import Path

# Patterns that marked the old hardcoded Azure wiring. Split so this file
# does not contain the strings it is looking for. The secret values
# themselves are intentionally not repeated here.
_FORBIDDEN = (
    "Instrumentation" + "Key=",
    "language-project" + ".cognitiveservices.azure.com",
)


def test_python_sources_do_not_embed_the_old_azure_wiring() -> None:
    offenders: list[str] = []
    for path in Path(".").rglob("*.py"):
        if any(part in {".venv", "venv", ".git", "__pycache__"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf8")
        for pattern in _FORBIDDEN:
            if pattern in text:
                offenders.append(f"{path}: {pattern}")
    assert offenders == []
