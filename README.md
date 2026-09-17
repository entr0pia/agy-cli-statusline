# agy-cli-statusline

English | [简体中文](README_ZH.md)

A lightweight, zero-dependency one-click installer and statusline/title manager for **Google Antigravity CLI** (`agy`).

It automatically places the custom `statusline.py` and `title.py` scripts into your `~/.gemini/antigravity-cli/scripts/` directory and initializes/updates the `statusLine` and `title` configurations in `~/.gemini/antigravity-cli/settings.json`.

---

## ✨ Features

- **Bilateral Screen-Adaptive Layout**: 
  - **Left**: Displays the current execution mode (e.g., `[Accept-Edits]`, `[Planning]`, `[Fast]`) highlighted in bold cyan. Automatically hides when unmatched or set to `default`, keeping the interface clean.
  - **Right**: Displays active model info with reasoning effort (e.g., `[Gemini 3.8 Flash · High]`), Context token usage & percentage, and live Quota remaining percentage.
- **Dynamic Warning Color Thresholds**:
  - **Context Usage**: Normal bold white; switches to **Bold Yellow** when usage reaches $\ge 20\%$; escalates to **Bold Red** when usage reaches $\ge 50\%$.
  - **Quota Remaining**: Normal bold white; switches to **Bold Yellow** when remaining falls $\le 50\%$; escalates to **Bold Red** when remaining falls $\le 20\%$.
- **Real-Time Terminal Title Integration**:
  - Automatically formats the window/tab title as `<workspace>: <emoji> <state> [<task_count>]` (e.g. `agy-cli-statusline: 🏃 working [2]`).
  - Native agent lifecycle emojis: `🚀 initializing`, `🤖 idle`, `🤔 thinking`, `🏃 working`, `🛠️ tool_use`.
- **Accurate Display Width Calculation**: Automatically strips ANSI escape sequences before calculating layout width and handles East Asian Wide characters (e.g., CJK) seamlessly, guaranteeing pixel-perfect alignment.
- **Zero Configuration & Zero Dependencies**: Built purely on the Python standard library. Runs instantly without downloading third-party pip packages.
- **Effortless `uvx` Execution**: Run directly via `uvx` without manual wheel building or packaging.

---

## 🖥️ Layout Preview

**Active Execution Mode (Bilateral layout):**
```text
[Accept-Edits]                                      [Gemini 3.8 Flash · High] | Context: 100.0k (10.0%) | Quota: 80.00%
```

**Unmatched / Default Mode (Clean right-aligned layout):**
```text
                                                    [Gemini 3.8 Flash · High] | Context: 100.0k (10.0%) | Quota: 80.00%
```

---

## 🚀 Usage

No manual compilation or wheel builds required. Simply execute using `uvx`:

### 1. One-Click Install & Configure

**Directly from GitHub (Recommended):**
```bash
uvx --from git+https://github.com/entr0pia/agy-cli-statusline agy-cli-statusline
```

**From a cloned local repository:**
```bash
uvx --from . agy-cli-statusline
```

> **What it does:**
> 1. Copies `statusline.py` and `title.py` scripts to `~/.gemini/antigravity-cli/scripts/`.
> 2. Automatically updates both `statusLine` and `title` sections in `~/.gemini/antigravity-cli/settings.json`.

### 2. Check Installation Status

```bash
uvx --from . agy-cli-statusline --status
```

### 3. Uninstall

```bash
uvx --from . agy-cli-statusline --uninstall
```

---

## ⚙️ Configuration Generated

After installation, your `~/.gemini/antigravity-cli/settings.json` is updated with:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python C:/Users/<Username>/.gemini/antigravity-cli/scripts/statusline.py",
    "enabled": true,
    "debug": false
  },
  "title": {
    "type": "command",
    "command": "python C:/Users/<Username>/.gemini/antigravity-cli/scripts/title.py",
    "enabled": true
  }
}
```

> **Debug Mode**: Setting `"debug": true` (or passing `--debug` during install, or setting environment variable `AGY_STATUSLINE_DEBUG=1`) will save the latest raw payload to `~/.gemini/antigravity-cli/last_statusline_payload.json` for troubleshooting. By default, debug writing is disabled to maximize rendering performance.

Restart `agy` in your terminal to see the new statusline and title in action!

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

