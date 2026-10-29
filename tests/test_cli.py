"""The batch review script exits clearly when Azure is not configured."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_cli_exits_when_credentials_are_missing() -> None:
    env = os.environ.copy()
    # Empty strings count as "set", so python-dotenv will not replace them from a local .env.
    env["AZURE_LANGUAGE_ENDPOINT"] = ""
    env["AZURE_LANGUAGE_KEY"] = ""
    env["COG_SERVICE_ENDPOINT"] = ""
    env["COG_SERVICE_KEY"] = ""

    script = Path("text-analytics-sdk/text-analysis.py")
    completed = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert completed.returncode == 1
    assert "not configured" in completed.stdout
    assert "AZURE_LANGUAGE_KEY" in completed.stdout
