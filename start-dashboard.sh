#!/usr/bin/env bash
#
# Start the Natural Language Planner dashboard (robust version).
#
# - Resolves the skill installation directory automatically
# - LOCKS the requested port (fails if unavailable after cleanup)
# - Runs the dashboard in the background with logging
# - Verifies the process is healthy before exiting
#
# Override skill location:  NLP_SKILL_PATH=/path/to/skill  or  SKILL_PATH=/path/to/skill
# Override port:            PORT=9000 ./start-dashboard.sh [workspace_path]
#
# Usage:
#   ./start-dashboard.sh [workspace_path]

set -euo pipefail

SKILL_NAME="natural-language-planner"
PORT="${PORT:-8080}"
LOG_FILE="/tmp/nlplanner-dashboard.log"

# ── Skill discovery ──────────────────────────────────────────────

is_skill_root() {
  [[ -f "$1/SKILL.md" && -d "$1/scripts" && -d "$1/templates" ]]
}

resolve_skill_root() {
  # 1. Explicit env var (NLP_SKILL_PATH takes priority, SKILL_PATH as alias)
  local env_path="${NLP_SKILL_PATH:-${SKILL_PATH:-}}"
  if [[ -n "$env_path" ]]; then
    local resolved
    resolved="$(cd "$env_path" 2>/dev/null && pwd)" || true
    if [[ -n "$resolved" ]] && is_skill_root "$resolved"; then
      echo "$resolved"
      return
    fi
    echo "ERROR: Skill path '$env_path' does not contain the expected files (SKILL.md, scripts/, templates/)." >&2
    exit 1
  fi

  # 2. Standard OpenClaw skill directory
  local openclaw_path="$HOME/.openclaw/skills/$SKILL_NAME"
  if [[ -d "$openclaw_path" ]] && is_skill_root "$openclaw_path"; then
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

  # 4. Relative to this script (local clone / checkout)
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if is_skill_root "$script_dir"; then
    echo "$script_dir"
    return
  fi

  echo "ERROR: $SKILL_NAME skill not found in any known location:" >&2
  echo "  1. NLP_SKILL_PATH / SKILL_PATH environment variable (not set)" >&2
  echo "  2. $openclaw_path" >&2
  echo "  3. pnpm global package ($(command -v pnpm &>/dev/null && pnpm root -g 2>/dev/null || echo 'pnpm not found'))" >&2
  echo "  4. $script_dir (this script's directory)" >&2
  echo "" >&2
  echo "FIX: Set NLP_SKILL_PATH=/path/to/skill and retry." >&2
  exit 1
}

# ── Port management ──────────────────────────────────────────────

check_port() {
  local port=$1
  if command -v lsof &>/dev/null; then
    ! lsof -i ":$port" &>/dev/null
  elif command -v ss &>/dev/null; then
    ! ss -tlnH "sport = :$port" 2>/dev/null | grep -q .
  else
    # Fallback: try to bind with Python
    python3 -c "
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(('0.0.0.0', $port)); s.close()
except OSError:
    sys.exit(1)
"
  fi
}

release_port() {
  local port=$1
  if command -v lsof &>/dev/null; then
    local pids
    pids="$(lsof -ti ":$port" 2>/dev/null)" || true
    if [[ -n "$pids" ]]; then
      echo "Releasing port $port (killing PIDs: $pids)..."
      echo "$pids" | xargs kill -9 2>/dev/null || true
      sleep 1
    fi
  fi
}

# ── Main ─────────────────────────────────────────────────────────

WORKSPACE="${1:-}"

SKILL_ROOT="$(resolve_skill_root)"
echo "Skill root: $SKILL_ROOT"

if [[ ! -d "$SKILL_ROOT/scripts" ]]; then
  echo "ERROR: Invalid skill directory — missing scripts/ at: $SKILL_ROOT" >&2
  exit 1
fi

if [[ -n "$WORKSPACE" && ! -d "$WORKSPACE" ]]; then
  echo "ERROR: Workspace not found: $WORKSPACE" >&2
  exit 1
fi

# Try to free the port if something is lingering
if ! check_port "$PORT"; then
  release_port "$PORT"
fi

if ! check_port "$PORT"; then
  echo "ERROR: Port $PORT is in use and could not be released." >&2
  echo "  Check what's using it:  lsof -i :$PORT  (or ss -tlnp sport = :$PORT)" >&2
  echo "  Kill it manually and retry." >&2
  exit 1
fi

# Build the workspace argument
WS_ARG=""
if [[ -n "$WORKSPACE" ]]; then
  WS_ARG="$WORKSPACE"
fi

# Start the dashboard in the background
nohup python3 "$SKILL_ROOT/dashboard-daemon.py" \
  --port "$PORT" --network \
  $WS_ARG \
  > "$LOG_FILE" 2>&1 &

DASHBOARD_PID=$!
echo "Started dashboard (PID $DASHBOARD_PID), waiting for it to come up..."
sleep 2

# Verify the process is alive
if ! kill -0 "$DASHBOARD_PID" 2>/dev/null; then
  echo "ERROR: Dashboard process exited immediately." >&2
  echo "  Logs: cat $LOG_FILE" >&2
  exit 1
fi

# Health check
if command -v curl &>/dev/null; then
  if curl -sf "http://127.0.0.1:$PORT/api/health" -o /dev/null 2>/dev/null; then
    echo "Dashboard confirmed live on port $PORT"
    echo "  PID:  $DASHBOARD_PID"
    echo "  Logs: tail -f $LOG_FILE"
  else
    echo "WARNING: Dashboard process is running but not yet responding on port $PORT." >&2
    echo "  It may still be starting up. Check logs: tail -f $LOG_FILE" >&2
  fi
else
  echo "Dashboard started (PID $DASHBOARD_PID). Install curl for health checks."
  echo "  Logs: tail -f $LOG_FILE"
fi
