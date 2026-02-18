#!/usr/bin/env python3
"""
Standalone launcher for the Natural Language Planner dashboard.

Resolves the skill installation directory automatically so this script
works whether the skill is:
  - Installed via symlink at ~/.openclaw/skills/natural-language-planner
  - Bundled inside the OpenClaw pnpm global package
  - Run directly from a local clone / checkout

Override the skill location with the NLP_SKILL_PATH environment variable
if auto-detection doesn't suit your setup.

Usage:
    python dashboard-daemon.py [--port PORT] [--network] [workspace_path]
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

SKILL_NAME = "natural-language-planner"
SKILL_MARKERS = ("SKILL.md", "scripts", "templates")


def _is_skill_root(path: Path) -> bool:
    return all((path / m).exists() for m in SKILL_MARKERS)


def _pnpm_global_root() -> "Path | None":
    pnpm = shutil.which("pnpm")
    if not pnpm:
        return None
    try:
        result = subprocess.run(
            [pnpm, "root", "-g"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def resolve_skill_root() -> Path:
    """
    Find the skill root using the same resolution order as
    ``config_manager.get_skill_root()``.
    """
    # 1. Explicit env var
    env = os.environ.get("NLP_SKILL_PATH")
    if env:
        p = Path(env).expanduser().resolve()
        if _is_skill_root(p):
            return p
        print(
            f"ERROR: NLP_SKILL_PATH='{env}' does not contain the expected "
            "skill files (SKILL.md, scripts/, templates/).",
            file=sys.stderr,
        )
        sys.exit(1)

    # 2. Standard OpenClaw skill directory
    openclaw_path = (Path.home() / ".openclaw" / "skills" / SKILL_NAME).resolve()
    if _is_skill_root(openclaw_path):
        return openclaw_path

    # 3. pnpm global package
    pnpm_root = _pnpm_global_root()
    if pnpm_root:
        for candidate in (
            pnpm_root / SKILL_NAME,
            pnpm_root / "openclaw" / "skills" / SKILL_NAME,
        ):
            resolved = candidate.resolve()
            if _is_skill_root(resolved):
                return resolved

    # 4. Relative to this script (works for local clones)
    here = Path(__file__).resolve().parent
    if _is_skill_root(here):
        return here

    searched = [
        f"  - NLP_SKILL_PATH env var (not set)",
        f"  - {openclaw_path}",
        f"  - pnpm global root ({pnpm_root or 'pnpm not found'})",
        f"  - {here}",
    ]
    print(
        "ERROR: Could not locate the natural-language-planner skill.\n"
        "Searched:\n" + "\n".join(searched) + "\n\n"
        "Set the NLP_SKILL_PATH environment variable to the directory "
        "containing SKILL.md, scripts/, and templates/.",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Natural Language Planner — Dashboard Daemon",
    )
    parser.add_argument("--port", type=int, default=None, help="Port (default: 8080)")
    parser.add_argument("--network", action="store_true", help="Bind to all interfaces (0.0.0.0)")
    parser.add_argument("workspace_path", nargs="?", default=None, help="Workspace directory")
    args = parser.parse_args()

    skill_root = resolve_skill_root()
    print(f"Skill root: {skill_root}")

    # Ensure the skill's scripts package is importable
    if str(skill_root) not in sys.path:
        sys.path.insert(0, str(skill_root))

    from scripts.utils import setup_logging
    from scripts.config_manager import set_config_path, load_config
    from scripts.dashboard_server import start_dashboard

    setup_logging()

    if args.workspace_path:
        set_config_path(args.workspace_path)
    else:
        config = load_config()
        if not config.get("workspace_path"):
            print(
                "No workspace specified. Pass a path or run 'init' first.",
                file=sys.stderr,
            )
            sys.exit(1)

    allow_network = args.network or None
    url = start_dashboard(port=args.port, allow_network=allow_network)
    if url:
        print(f"Dashboard running at {url}")
        print("Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping dashboard.")
    else:
        print("Failed to start dashboard.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
