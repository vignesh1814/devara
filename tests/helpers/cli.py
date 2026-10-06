"""How tests invoke the compiler CLI as a subprocess.

POSIX hosts run the ``devara`` bash wrapper. Windows cannot execute that script
(WinError 193), and ``devara.cmd`` would pass arguments through cmd.exe quoting,
so there the CLI module is run directly with the current interpreter.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DEVARA_CMD: list[str] = (
    [str(ROOT / "devara")] if os.name == "posix" else [sys.executable, "-m", "compiler.cli"]
)
