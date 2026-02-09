# Natural Language Planner

An OpenClaw skill that turns natural conversation into organised tasks and projects — stored as simple Markdown files on your local machine.

## What It Does

- **Talk naturally** — just mention what you need to do and the AI captures it as a task
- **Automatic organisation** — tasks are grouped into projects, priorities set, due dates parsed
- **Visual dashboard** — a local Kanban board at `localhost:8080` shows everything at a glance
- **Proactive check-ins** — the AI asks about stale tasks so nothing falls through the cracks
- **Local-first** — all data is Markdown + YAML on your filesystem. No accounts, no cloud, no lock-in

## Quick Start

### 1. Install the dependency

```bash
pip install pyyaml
```

### 2. Add the skill to your AI assistant

Copy or clone this directory into your skills folder. The AI will detect the
`SKILL.md` and activate the planner automatically.

### 3. Start using it

Just talk to your AI assistant:

> "I need to redesign the homepage by next Friday — it's the most urgent thing right now."

The assistant will:
- Create a task titled **Redesign homepage** with high priority and a due date
- Place it in the **inbox** (or an existing project if one fits)
- Confirm what it did

### 4. Open the dashboard (optional)

Ask the assistant to start the dashboard, or run:

```python
from scripts.dashboard_server import start_dashboard
start_dashboard()  # → http://localhost:8080
```

## Workspace Structure

All your data lives in one directory (default `~/nlplanner`):

```
~/nlplanner/
├── .nlplanner/          # Config and dashboard files
│   └── config.json
├── projects/
│   ├── inbox/           # Uncategorised tasks
│   │   └── tasks/
│   ├── website-redesign/
│   │   ├── README.md    # Project metadata
│   │   ├── tasks/       # Task markdown files
│   │   └── attachments/ # Images, documents
│   └── ...
└── archive/             # Archived projects and tasks
```

Every task and project is a Markdown file with YAML frontmatter — readable
and editable in any text editor.

## Configuration

Settings live in `.nlplanner/config.json`:

| Setting | Default | Description |
|---|---|---|
| `checkin_frequency_hours` | 24 | How often to ask about stale tasks |
| `auto_archive_completed_days` | 30 | Days before done tasks auto-archive |
| `default_priority` | `"medium"` | Default priority for new tasks |
| `dashboard_port` | 8080 | Port for the local dashboard |

## Dashboard Features

The browser-based dashboard includes:

- **Kanban board** — drag-free columns for To Do, In Progress, Done
- **Project overview** — cards showing each project with task counts
- **Timeline** — upcoming deadlines sorted by date
- **Search** — find any task instantly
- **Task detail modal** — click to see full task info
- **Auto-refresh** — updates every 5 seconds

## Requirements

- **Python 3.9+**
- **PyYAML** (`pip install pyyaml`)
- No other external dependencies for core functionality

## Project Structure

```
natural-language-planner/
├── SKILL.md              # AI skill instructions
├── scripts/
│   ├── file_manager.py   # CRUD for projects and tasks
│   ├── config_manager.py # Settings management
│   ├── index_manager.py  # Search and lookup
│   ├── dashboard_server.py # Local web server
│   └── utils.py          # Shared utilities
├── templates/
│   ├── dashboard/        # HTML/CSS/JS for the dashboard
│   ├── project_template.md
│   └── task_template.md
├── tests/                # Unit tests
└── examples/             # Sample data and conversations
```

## Contributing

Contributions are welcome! Here's how:

1. **Fork** this repository
2. Create a **feature branch** (`git checkout -b feature/my-idea`)
3. Make your changes and add tests
4. Submit a **pull request** with a clear description

### Development

```bash
# Run tests
python -m pytest tests/ -v

# Start dashboard in development
python -c "from scripts.dashboard_server import start_dashboard; start_dashboard(); input('Press Enter to stop')"
```

### Areas for contribution

- Better natural date parsing
- Drag-and-drop in the Kanban board
- Export to other formats (JSON, CSV)
- Import from Todoist / Notion / other tools
- CLI interface
- Time tracking

## Design Principles

1. **Local-first** — your data never leaves your machine
2. **Human-readable** — everything is Markdown you can edit by hand
3. **Non-destructive** — archive, never delete
4. **Minimal dependencies** — stdlib where possible
5. **Cross-platform** — works on Windows, macOS, and Linux

## License

MIT — see [LICENSE.txt](LICENSE.txt)
