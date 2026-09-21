# AGENTS.md

## Project Overview

**agy-cli-statusline** is a lightweight, zero-dependency one-click installer and statusline/title manager for **Google Antigravity CLI** (`agy`).

It automatically copies and synchronizes custom `statusline.py` and `title.py` scripts into `~/.gemini/antigravity-cli/scripts/` and manages the `statusLine` and `title` configurations within `~/.gemini/antigravity-cli/settings.json`.

### Key Capabilities
- **Bilateral Statusline**: Left-aligned execution mode (e.g. `[Accept-Edits]`, `[Planning]`, `[Fast]`) and right-aligned model info (`[Gemini 3.8 Flash · High]`), context token usage, and quota availability.
- **Dynamic Theme Palette & Custom Colors**: Automatically adapts execution mode accent color to `colorScheme` (`tokyo night`, `solarized dark/light`, `light`, `dark`, `terminal`, `colorblind-friendly`), or user-defined `statusLine.themeColor` hex/name.
- **Dynamic Warning Thresholds**: Context token usage escalates to bold yellow at $\ge 20\%$ and bold red at $\ge 50\%$; remaining quota drops to bold yellow at $\le 50\%$ and bold red at $\le 20\%$.
- **Terminal Title Sync**: Real-time terminal title formatted as `<workspace>: <emoji> <state> [<task_count>]` across agent lifecycle states (`initializing`, `idle`, `thinking`, `working`, `tool_use`).
- **Precision Alignment**: Accurate visible column width calculation handling East Asian (CJK) characters and ANSI escape sequences.
- **Zero Dependencies**: Pure Python standard library only. No external packages required at runtime or installation.

---

## Directory & File Structure

```text
agy-cli-statusline/
├── pyproject.toml                     # Build configuration and project metadata (uv_build backend)
├── uv.lock                            # uv lockfile for deterministic environments
├── .python-version                    # Targeted Python version (3.12)
├── README.md                          # Human-oriented English documentation
├── README_ZH.md                       # Human-oriented Chinese documentation
├── LICENSE                            # MIT license
├── AGENTS.md                          # Agent guidance and technical reference (this file)
└── src/
    └── agy_cli_statusline/
        ├── __init__.py                # Package exports (main, cli_main, install, uninstall, status)
        ├── installer.py               # CLI entrypoint, path resolution, settings.json updater
        ├── statusline.py              # Standalone statusline renderer (invoked via stdin JSON by agy)
        └── title.py                   # Standalone terminal title updater (invoked via stdin JSON by agy)
```

---

## Setup & Development Environment

The project requires **Python $\ge$ 3.12** and uses **`uv`** as the primary package and project manager.

### Prerequisites & Dependency Management
- Initialize environment and sync virtualenv:
  ```powershell
  uv sync
  ```
- Run the CLI entrypoint directly:
  ```powershell
  uv run agy-cli-statusline --help
  ```
- Build distribution wheels and source tarball:
  ```powershell
  uv build
  ```
  Artifacts will be output to `dist/`.

---

## Core Workflows & Commands

### 1. CLI Commands (Installer)
All operations can be executed via `uv run agy-cli-statusline` or via `uvx --from . agy-cli-statusline`:

- **Install / Update (Dry Run)**:
  ```powershell
  uv run agy-cli-statusline install --dry-run
  ```
- **Install / Update (Live)**:
  ```powershell
  uv run agy-cli-statusline install
  ```
- **Install with Debug Logging Enabled**:
  ```powershell
  uv run agy-cli-statusline install --debug
  ```
- **Inspect Installation & Configuration Status**:
  ```powershell
  uv run agy-cli-statusline status
  ```
- **Uninstall (Remove settings and delete scripts)**:
  ```powershell
  uv run agy-cli-statusline uninstall
  ```
- **Uninstall (Dry Run)**:
  ```powershell
  uv run agy-cli-statusline uninstall --dry-run
  ```
- **Uninstall (Keep script files, remove settings only)**:
  ```powershell
  uv run agy-cli-statusline uninstall --keep-script
  ```

### 2. Testing Standalone Runtime Scripts

Both `statusline.py` and `title.py` are executed by `agy` via standard input piping. Test them with mock JSON payloads directly:

- **Test `title.py`**:
  ```powershell
  '{"agent_state": "working", "workspace": {"project_dir": "C:/demo/project"}, "task_count": 2}' | uv run python -m agy_cli_statusline.title
  ```
  *Expected Output:*
  ```text
  project: 🏃 working [2]
  ```

- **Test `statusline.py`**:
  ```powershell
  '{"context_window": {"total_input_tokens": 102400, "used_percentage": 10.0}, "model": {"display_name": "Gemini 3.8 Flash (High)"}, "execution_mode": "accept_edits"}' | uv run python -m agy_cli_statusline.statusline
  ```

- **Test fallback on empty input**:
  ```powershell
  '' | uv run python -m agy_cli_statusline.title
  # Expected: unknown: 😴 idle
  ```

---

## Architecture Details

### 1. `installer.py`
- **Path Resolution**:
  - Configuration directory resolved from `ANTIGRAVITY_CONFIG_DIR`, `AGY_CONFIG_DIR`, or default `Path.home() / ".gemini" / "antigravity-cli"`.
  - Target scripts placed in `<agy_dir>/scripts/statusline.py` and `<agy_dir>/scripts/title.py`.
  - Configuration file targeted at `<agy_dir>/settings.json`.
- **Script Extraction**:
  - Bundled scripts are read using `importlib.resources.files("agy_cli_statusline")` with a relative filesystem fallback to `Path(__file__).parent`.
- **Atomic & Resilient Settings Update**:
  - Existing settings in `settings.json` are preserved.
  - If `settings.json` is corrupted or invalid JSON, a `.bak` backup file is generated before reset.
  - Injected command paths use forward slashes (`as_posix()`) and are quoted if spaces are present.

### 2. `statusline.py`
- **Input Payload**: Receives JSON containing `context_window`, `model`, `quota`, `execution_mode`, `terminal_width`.
- **Display Width Calculation**:
  - ANSI escape sequences are stripped via `ANSI_ESCAPE_RE`.
  - `unicodedata.east_asian_width()` evaluates full-width characters (`'F'`, `'W'`) as 2 units, ensuring bilateral gap calculation is aligned.
- **Color Threshold Logic**:
  - Context Tokens: Yellow at $\ge 20\%$, Red at $\ge 50\%$.
  - Quota Remaining: Yellow at $\le 50\%$, Red at $\le 20\%$. Supports sliding 5-hour quota (`gemini-5h`, `3p-5h`), remaining fractions, remaining percentages, and total credits.
- **Execution Mode**:
  - Extracted from `execution_mode`, `cycle_mode`, or `agent_mode`. Suppressed when `None`, empty, or `"default"`.
- **Dynamic Theme & Accent Color Resolution**:
  - Priority: `statusLine.themeColor`/`color` in `settings.json` $\rightarrow$ `AGY_THEME_COLOR` env var $\rightarrow$ `colorScheme` palette lookup (`tokyo night`, `solarized`, `light`, etc.) $\rightarrow$ fallback default (`\033[1;96m`).
  - Supports 24-bit TrueColor (`#7aa2f7`), standard ANSI color names (`purple`, `cyan`, etc.), and raw ANSI codes.
- **Debug File Writing**:
  - Payload logging to `last_statusline_payload.json` only occurs if debug is enabled via `AGY_STATUSLINE_DEBUG=1` or `settings.json` `statusLine.debug: true`.

### 3. `title.py`
- **Latency Optimization**:
  - Input stream reconfigured to `utf-8-sig` to automatically discard BOM headers.
  - Path basename extracted using pure string slice `rfind` operations rather than `os.path.normpath` or regex.
  - Direct output via `sys.stdout.write` instead of `print` to minimize overhead on rapid terminal refreshes.
- **State Mappings**:
  - `initializing` $\rightarrow$ `🚀`
  - `idle` $\rightarrow$ `🤖`
  - `thinking` $\rightarrow$ `🤔`
  - `working` $\rightarrow$ `🏃`
  - `tool_use` $\rightarrow$ `🛠️`

---

## Code Style & Architectural Guidelines

- **Strict Zero External Dependencies**:
  - Never introduce external libraries (e.g. `click`, `rich`, `typer`, `pydantic`). The entire package must run on the standard library of Python 3.12+.
- **Windows Console & UTF-8 Compatibility**:
  - Always ensure `sys.stdout.reconfigure(encoding="utf-8")` and `sys.stdin.reconfigure(encoding="utf-8")` or `utf-8-sig` are called on startup.
  - Windows console virtual terminal processing (`ENABLE_VIRTUAL_TERMINAL_PROCESSING`, `0x0004`) should be enabled via `ctypes.windll.kernel32` for ANSI escape sequence support.
- **Performance Constraints**:
  - Both `statusline.py` and `title.py` are executed repeatedly on interactive keystrokes and agent state transitions. Keep import footprint minimal and avoid subprocess invocations.
- **Non-destructive Configuration Management**:
  - When modifying `settings.json`, preserve all unmanaged keys (e.g., custom hotkeys, themes, model settings).
  - Use 2-space indentation and ensure trailing newlines when writing JSON.

---

## Contribution & Pull Request Guidelines

1. **Verification Checklist**:
   - [ ] Run `uv run agy-cli-statusline install --dry-run` and confirm successful simulated run.
   - [ ] Run `uv run agy-cli-statusline status` and verify clean diagnostic output.
   - [ ] Verify both `title.py` and `statusline.py` with mock piped JSON input.
   - [ ] Run `uv build` to ensure package wheels build without warnings or errors.
   - [ ] Confirm no new external dependencies were introduced in `pyproject.toml`.
2. **Commit Conventions**:
   - Follow Conventional Commits:
     - `feat:` for new capabilities (e.g., new statusline badge or quota provider).
     - `fix:` for bug fixes (e.g., encoding, terminal width calculation).
     - `perf:` for latency or execution speed optimizations.
     - `docs:` for documentation updates.
     - `refactor:` for code restructuring without behavioral change.
