"""
Local web server for the Natural Language Planner dashboard.

Serves the dashboard single-page app and provides a JSON API for
reading task/project data from the workspace.

Uses only the Python standard library (http.server) so there are no
external dependencies.  For production-style usage consider replacing
with FastAPI or similar, but this works great for local use.
"""

import json
import logging
import mimetypes
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, parse_qs, unquote

from .config_manager import load_config
from .file_manager import list_projects, list_tasks, get_project, get_task
from .index_manager import rebuild_index, get_stats, search_tasks, get_tasks_due_soon, get_overdue_tasks

logger = logging.getLogger("nlplanner.dashboard")

_server: Optional[HTTPServer] = None
_thread: Optional[threading.Thread] = None


class DashboardHandler(SimpleHTTPRequestHandler):
    """
    HTTP request handler for the dashboard.

    Serves static files from the dashboard directory and handles
    /api/* routes for JSON data.
    """

    def __init__(self, *args, dashboard_dir: str = "", **kwargs):
        self._dashboard_dir = dashboard_dir
        super().__init__(*args, directory=dashboard_dir, **kwargs)

    def do_GET(self) -> None:
        """Route GET requests to the appropriate handler."""
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self._handle_api(path, parsed.query)
        else:
            # Serve static files from the dashboard directory
            super().do_GET()

    def _handle_api(self, path: str, query_string: str) -> None:
        """Dispatch API requests."""
        params = parse_qs(query_string)

        routes: dict[str, Any] = {
            "/api/stats": self._api_stats,
            "/api/projects": self._api_projects,
            "/api/tasks": self._api_tasks,
            "/api/search": self._api_search,
            "/api/due-soon": self._api_due_soon,
            "/api/overdue": self._api_overdue,
        }

        # Dynamic routes: /api/project/<id>, /api/task/<id>, /api/attachment/<project>/<file>
        if path.startswith("/api/attachment/"):
            parts = path.split("/api/attachment/")[1].strip("/").split("/", 1)
            if len(parts) == 2:
                self._api_serve_attachment(unquote(parts[0]), unquote(parts[1]))
            else:
                self._json_response({"error": "Bad attachment path"}, status=400)
            return
        if path.startswith("/api/project/"):
            project_id = path.split("/api/project/")[1].strip("/")
            self._api_single_project(project_id)
            return
        if path.startswith("/api/task/"):
            task_id = path.split("/api/task/")[1].strip("/")
            self._api_single_task(task_id)
            return

        handler = routes.get(path)
        if handler:
            handler(params)
        else:
            self._json_response({"error": "Not found"}, status=404)

    # ── API handlers ───────────────────────────────────────────

    def _api_stats(self, params: dict) -> None:
        rebuild_index()
        self._json_response(get_stats())

    def _api_projects(self, params: dict) -> None:
        projects = list_projects()
        self._json_response(projects)

    def _api_tasks(self, params: dict) -> None:
        project = params.get("project", [None])[0]
        status = params.get("status", [None])[0]
        priority = params.get("priority", [None])[0]

        filters: dict[str, Any] = {}
        if status:
            filters["status"] = status
        if priority:
            filters["priority"] = priority

        tasks = list_tasks(filter_by=filters if filters else None, project_id=project)
        self._json_response(tasks)

    def _api_search(self, params: dict) -> None:
        query = params.get("q", [""])[0]
        if not query:
            self._json_response([])
            return
        rebuild_index()
        results = search_tasks(query)
        self._json_response(results)

    def _api_due_soon(self, params: dict) -> None:
        days = int(params.get("days", ["7"])[0])
        rebuild_index()
        self._json_response(get_tasks_due_soon(days))

    def _api_overdue(self, params: dict) -> None:
        rebuild_index()
        self._json_response(get_overdue_tasks())

    def _api_single_project(self, project_id: str) -> None:
        project = get_project(project_id)
        if project:
            self._json_response(project)
        else:
            self._json_response({"error": "Project not found"}, status=404)

    def _api_single_task(self, task_id: str) -> None:
        task = get_task(task_id)
        if task:
            self._json_response(task)
        else:
            self._json_response({"error": "Task not found"}, status=404)

    def _api_serve_attachment(self, project_id: str, filename: str) -> None:
        """Serve a file from a project's attachments/ directory."""
        config = load_config()
        ws = config.get("workspace_path", "")
        if not ws:
            self._json_response({"error": "Workspace not configured"}, status=500)
            return

        # Security: prevent path traversal
        safe_name = Path(filename).name
        file_path = Path(ws) / "projects" / project_id / "attachments" / safe_name

        if not file_path.is_file():
            self._json_response({"error": "Attachment not found"}, status=404)
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or "application/octet-stream"

        try:
            data = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, max-age=300")
            self.end_headers()
            self.wfile.write(data)
        except OSError as e:
            logger.error("Failed to serve attachment %s: %s", file_path, e)
            self._json_response({"error": "Failed to read file"}, status=500)

    # ── Response helpers ───────────────────────────────────────

    def _json_response(self, data: Any, status: int = 200) -> None:
        """Send a JSON response."""
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Redirect access logs to our logger instead of stderr."""
        logger.debug(format, *args)


# ── Public functions ───────────────────────────────────────────────

def _resolve_dashboard_dir() -> str:
    """
    Find the dashboard static files directory.

    Looks in the workspace .nlplanner/dashboard first, then falls back to
    the templates/dashboard shipped with the skill.
    """
    config = load_config()
    ws = config.get("workspace_path", "")

    if ws:
        ws_dashboard = Path(ws) / ".nlplanner" / "dashboard"
        if (ws_dashboard / "index.html").exists():
            return str(ws_dashboard)

    # Fallback: templates directory relative to this script
    templates = Path(__file__).parent.parent / "templates" / "dashboard"
    if (templates / "index.html").exists():
        return str(templates)

    logger.warning("Dashboard files not found. Serving from current directory.")
    return "."


def start_dashboard(port: Optional[int] = None) -> str:
    """
    Start the dashboard web server in a background thread.

    Args:
        port: Port number (default: from config or 8080).

    Returns:
        The dashboard URL.

    Example:
        >>> url = start_dashboard()
        >>> print(url)
        http://localhost:8080
    """
    global _server, _thread

    if _server is not None:
        logger.info("Dashboard is already running.")
        return get_dashboard_url()

    if port is None:
        config = load_config()
        port = config.get("settings", {}).get("dashboard_port", 8080)

    dashboard_dir = _resolve_dashboard_dir()
    handler = partial(DashboardHandler, dashboard_dir=dashboard_dir)

    try:
        _server = HTTPServer(("127.0.0.1", port), handler)
    except OSError as e:
        logger.error("Could not start dashboard on port %d: %s", port, e)
        return ""

    _thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _thread.start()

    url = f"http://localhost:{port}"
    logger.info("Dashboard started at %s (serving from %s)", url, dashboard_dir)
    return url


def stop_dashboard() -> None:
    """Stop the running dashboard server."""
    global _server, _thread

    if _server is None:
        logger.info("Dashboard is not running.")
        return

    _server.shutdown()
    _server = None
    _thread = None
    logger.info("Dashboard stopped.")


def get_dashboard_url() -> str:
    """
    Get the URL of the running dashboard.

    Returns:
        The dashboard URL, or an empty string if not running.
    """
    if _server is None:
        return ""
    host, port = _server.server_address
    return f"http://localhost:{port}"


def is_running() -> bool:
    """Check whether the dashboard server is currently running."""
    return _server is not None
