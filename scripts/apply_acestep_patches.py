"""Apply Musicia's reviewed ACE-Step patch before starting its local process.

Only exact original or exact patched hunks are accepted. A changed upstream
implementation must be reviewed; no fuzzy replacements, git or pip are used.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PATCH_FILE = Path(__file__).with_name("patches") / "acestep_vae_cpu_dtype.patch"
TARGET_FILE = Path("acestep/core/generation/handler/generate_music_decode.py")


def patch_hunks(patch_text: str) -> list[tuple[str, str]]:
    """Read exact before/after blocks and validate unified hunk line counts."""
    hunks = []
    old_lines: list[str] = []
    new_lines: list[str] = []
    expected = None
    for line in patch_text.splitlines(keepends=True):
        if line.startswith("@@"):
            if expected is not None:
                if (len(old_lines), len(new_lines)) != expected:
                    raise ValueError("Invalid patch hunk line counts")
                hunks.append(("".join(old_lines), "".join(new_lines)))
            match = re.match(r"@@ -\d+,(\d+) \+\d+,(\d+) @@", line)
            if match is None:
                raise ValueError("Invalid patch hunk header")
            expected = (int(match[1]), int(match[2]))
            old_lines, new_lines = [], []
        elif expected is not None:
            if line.startswith(" "):
                old_lines.append(line[1:])
                new_lines.append(line[1:])
            elif line.startswith("-"):
                old_lines.append(line[1:])
            elif line.startswith("+"):
                new_lines.append(line[1:])
            else:
                raise ValueError("Invalid patch hunk content")
    if expected is None or (len(old_lines), len(new_lines)) != expected:
        raise ValueError("Missing or incomplete patch hunks")
    hunks.append(("".join(old_lines), "".join(new_lines)))
    return hunks


def apply_patch(engine_root: Path) -> str:
    """Apply once, leave already patched source untouched, reject unknown source."""
    target = engine_root / TARGET_FILE
    original_bytes = target.read_bytes()
    source = original_bytes.decode("utf-8").replace("\r\n", "\n")
    hunks = patch_hunks(PATCH_FILE.read_text(encoding="utf-8"))
    states = []
    for before, after in hunks:
        if source.count(after) == 1 and source.count(before) == 0:
            states.append("patched")
        elif source.count(before) == 1 and source.count(after) == 0:
            states.append("original")
        else:
            raise ValueError(f"Unknown ACE-Step decode source: {target}; review the upstream change before starting")
    if all(state == "patched" for state in states):
        return "already-applied"
    if any(state != "original" for state in states):
        raise ValueError(f"Partially patched ACE-Step decode source: {target}; review before starting")
    for before, after in hunks:
        source = source.replace(before, after, 1)
    compile(source, str(target), "exec")
    newline = "\r\n" if b"\r\n" in original_bytes else "\n"
    patched_bytes = source.replace("\n", newline).encode("utf-8")
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name + ".", suffix=".tmp", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(patched_bytes)
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return "applied"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-root", type=Path, default=PROJECT_ROOT / "vendor" / "ACE-Step-1.5")
    args = parser.parse_args()
    try:
        state = apply_patch(args.engine_root)
    except (OSError, UnicodeError, ValueError, SyntaxError) as exc:
        print(f"ACE-Step CPU VAE patch failed: {exc}", file=sys.stderr)
        return 1
    print(f"ACE-Step CPU VAE patch: {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
