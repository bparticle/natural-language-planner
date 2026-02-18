#!/usr/bin/env bash
#
# Start the Natural Language Planner dashboard.
#
# Resolves the skill installation directory automatically so this script
# works whether the skill is:
#   - Installed via symlink at ~/.openclaw/skills/natural-language-planner
#   - Bundled inside the OpenClaw pnpm global package
#   - Run directly from a local clone / checkout
#
# Override the skill location:
#   NLP_SKILL_PATH=/path/to/skill ./start-dashboard.sh [OPTIONS]
#
# Usage:
#   ./start-dashboard.sh [--port PORT] [--network] [workspace_path]

set -euo pipefail

SKILL_NAME="natural-language-planner"

is_skill_root() {
  [[ -f "$1/SKILL.md" && -d "$1/scripts" && -d "$1/templates" ]]
}

resolve_skill_root() {
  # 1. Explicit env var
  if [[ -n "${NLP_SKILL_PATH:-}" ]]; then
    local resolved
    resolved="$(cd "$NLP_SKILL_PATH" 2>/dev/null && pwd)" || true
    if [[ -n "$resolved" ]] && is_skill_root "$resolved"; then
      echo "$resolved"
      return
    fi
    echo "ERROR: NLP_SKILL_PATH='$NLP_SKILL_PATH' does not contain the expected skill files." >&2
    exit 1
  fi

  # 2. Standard OpenClaw skill directory
  local openclaw_path="$HOME/.openclaw/skills/$SKILL_NAME"
  if is_skill_root "$openclaw_path"; then
    echo "$(cd "$openclaw_path" && pwd)"
    return
  fi

  # 3. pnpm global package
  if command -v pnpm &>/dev/null; then
    local pnpm_root
    pnpm_root="$(pnpm root -g 2>/dev/null)" || true
    if [[ -n "$pnpm_root" ]]; then
      for candidate in \
        "$pnpm_root/$SKILL_NAME" \
        "$pnpm_root/openclaw/skills/$SKILL_NAME"; do
        if [[ -d "$candidate" ]] && is_skill_root "$candidate"; then
          echo "$(cd "$candidate" && pwd)"
          return
        fi
      done
    fi
  fi

  # 4. Relative to this script
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if is_skill_root "$script_dir"; then
    echo "$script_dir"
    return
  fi

  echo "ERROR: Could not locate the $SKILL_NAME skill." >&2
  echo "Searched:" >&2
  echo "  - NLP_SKILL_PATH env var (not set)" >&2
  echo "  - $openclaw_path" >&2
  echo "  - pnpm global root ($(command -v pnpm &>/dev/null && pnpm root -g 2>/dev/null || echo 'pnpm not found'))" >&2
  echo "  - $script_dir" >&2
  echo "" >&2
  echo "Set the NLP_SKILL_PATH environment variable to the directory" >&2
  echo "containing SKILL.md, scripts/, and templates/." >&2
  exit 1
}

SKILL_ROOT="$(resolve_skill_root)"
echo "Skill root: $SKILL_ROOT"

cd "$SKILL_ROOT"
exec python3 -m scripts dashboard "$@"
