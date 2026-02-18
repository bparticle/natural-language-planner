# False positive: natural-language-planner (bparticle/natural-language-planner) flagged as suspicious

## Summary

My skill [`natural-language-planner`](https://clawhub.ai/bparticle/natural-language-planner) (v0.1.0) is flagged as suspicious. VirusTotal marks it benign; OpenClaw flags it with an error. This is a false positive — the flagged patterns are standard and necessary for the skill's purpose.

**Repo:** https://github.com/bparticle/natural-language-planner

## What the skill does

A local-first task and project manager. Captures tasks from conversation, stores them as Markdown+YAML files on the user's machine, and serves a Kanban dashboard via a local HTTP server. Everything runs locally — no data leaves the machine unless the user explicitly enables tunneling.

## Why the scanner likely flagged it

The skill ships a `scripts/` directory with Python modules. Here are the patterns that likely triggered the scan, and why each is benign:

### 1. `subprocess.Popen` (in `scripts/tunnel.py`)

Used to launch well-known tunnel tools (`cloudflared`, `ngrok`, `localtunnel`) as child processes. Commands are **hardcoded** — no user-supplied strings are interpolated into commands:

```python
cmd = ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"]
```

The `port` argument is an integer. There is no shell execution (`shell=True` is never used).

### 2. HTTP server + socket operations (in `scripts/dashboard_server.py`)

A `http.server`-based dashboard serving local task data. Binds to `127.0.0.1` by default — LAN access is opt-in and documented with warnings. Socket usage is limited to port availability checks and LAN IP detection.

### 3. Extensive file I/O (across modules)

The entire storage model is local Markdown files. All file operations use:
- `safe_child_path()` — resolves and verifies paths stay within the workspace root via `Path.is_relative_to()`, preventing path traversal
- `safe_read_file()` / `safe_write_file()` — wrappers with error handling
- `Path.name` sanitization on URL-derived parameters for attachment serving

### 4. `sys.path.insert` in SKILL.md examples

The SKILL.md contains code examples showing the AI agent how to import the skill's modules. This is standard practice for skills that ship Python code — the path points to the skill's own `scripts/` directory.

### 5. YAML parsing

Uses `yaml.safe_load()` exclusively — never `yaml.load()`.

## Security measures in place

- **Path traversal protection:** `safe_child_path()` validates all constructed paths stay within the workspace root
- **Input validation:** `validate_status()`, `validate_priority()`, slug sanitization via regex
- **No arbitrary code execution:** subprocess commands are hardcoded arrays, no `shell=True`, no `eval()`/`exec()`
- **Localhost by default:** dashboard and API only bind to `127.0.0.1`
- **Safe deserialization:** `yaml.safe_load()` only
- **Unit tests:** `tests/` directory with coverage for core modules

## Request

Please reclassify this skill as benign.
