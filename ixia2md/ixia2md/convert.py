"""Run DITA-OT to turn a DITA map into Markdown."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import FLAVORS, Config


class ConvertError(Exception):
    """DITA-OT failed. The message is safe to show to a user (it names the first error line)."""


def run_dita_ot(cfg: Config, root_map: Path, out_dir: Path, flavor: str, log_path: Path, timeout: int = 1800) -> None:
    if flavor not in FLAVORS:
        raise ConvertError(f"Unknown Markdown flavor '{flavor}'. Choose one of: {', '.join(FLAVORS)}.")
    exe = cfg.dita_executable()
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(exe), "--input", str(root_map), "--format", flavor, "--output", str(out_dir)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ConvertError(f"DITA-OT did not finish within {timeout // 60} minutes.") from None
    except OSError as e:
        raise ConvertError(f"Could not start DITA-OT: {e}") from None
    # Drop the JVM banner line so the log stays readable.
    text = "\n".join(l for l in (p.stdout + "\n" + p.stderr).splitlines() if not l.startswith("Picked up JAVA_TOOL_OPTIONS"))
    log_path.write_text(text, encoding="utf-8")
    if p.returncode != 0:
        first = next((l for l in text.splitlines() if "[DOTJ" in l and "[ERROR]" in l or l.startswith("Error:")), "")
        raise ConvertError("DITA-OT reported an error. " + (first.strip()[:300] or "See conversion.log."))
