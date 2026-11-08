# Antigravity CLI (`agy`) Architecture & Internal Modules

This reference details the core architecture and code organization of the Google Antigravity CLI (`agy`) recovered via Go symbol table reconstruction.

---

## 1. Google3 Package Hierarchy

The `agy` binary is compiled from Google internal monorepo packages under `google3/third_party/jetski/cli/*`:

```text
google3/third_party/jetski/cli/
├── commands/           # Slash commands implementation (/title, /statusline, /model, /skills, etc.)
│   ├── commands.(*titleCommand)
│   ├── commands.(*statuslineCommand)
│   └── ...
├── store/              # Central state management & lifecycle orchestration
│   ├── store.(*Manager)            # Manages runners, timers, event pub/sub
│   ├── store.(*Store)              # In-memory session state, workspace, conversations
│   ├── store.(*StatusLineRunner)   # Subprocess runner for statusline & title IPC
│   ├── store.BuildStatusLineData   # Constructs StatusLineData payload
│   └── store.uiPhaseToAgentState   # Inlined UIPhase -> agent_state jump table
├── model/              # Bubbletea TUI presentation models & views
│   ├── model.(*RootModel)
│   ├── model.StatusLineModel
│   └── model.<Phase>Model          # View models for each UIPhase
├── types/              # Domain types, settings, and JSON-marshaled structs
│   ├── types.StatusLineData
│   ├── types.CliSetting
│   └── types.StatusLineConfig
├── backend/            # RPC clients connecting to local/remote language servers
└── graphic/            # Terminal capabilities & graphics protocol detector (Kitty, iTerm, Sixel)
```

---

## 2. IPC Subprocess Execution Model (`StatusLineRunner`)

Both `statusLine` and `title` hooks in `settings.json` share the exact same execution runner: [`StatusLineRunner`](file:///C:/Users/Peyton/AppData/Local/agy/bin/agy.exe).

### Lifecycle & Concurrency
1. **Triggering**:
   - `triggerTitleUpdate`: triggered upon every UI phase transition or background task state update.
   - `triggerStatusLineUpdate`: triggered on keystrokes, token updates, and layout resize.
2. **Payload Serialization**:
   - [`StatusLineRunner.run`](file:///C:/Users/Peyton/AppData/Local/agy/bin/agy.exe) invokes `encoding/json/v2.Marshal` on `*types.StatusLineData`.
3. **Execution**:
   - The command configured in `settings.json` is executed using `os/exec.CommandContext` with a timeout context.
   - Serialized JSON bytes are piped to `stdin`.
4. **Stdout Capturing**:
   - Output from `stdout` is captured and trimmed (`strings.TrimRight(..., "\n")`).
   - For `title`, ANSI escape sequences or OSC escape codes (`\033]0;...\007`) are written to the terminal title bar.
   - For `statusline`, the string is rendered at the bottom bar of the interactive screen.

---

## 3. Key Reverse-Engineering Insights

- **Shared Data Pipeline**:
  `title` and `statusLine` do not have separate data builders; both receive the exact same payload built by `store.BuildStatusLineData`.
- **Inlining Characteristics**:
  Helper functions like `uiPhaseToAgentState` and `snakeToTitle` are aggressively inlined by the Go compiler into `store.BuildStatusLineData`. They appear in the assembly as local jump tables rather than distinct `CALL` instructions.
- **Go 1.20+ `pclntab` Layout**:
  Go binaries on Windows store pclntab in the `.rdata` PE section with magic `0xfffffff1`. The function name table (`funcnametab`) provides unmodified package and symbol names even when stripped of DWARF symbols.
