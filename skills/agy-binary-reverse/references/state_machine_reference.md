# Antigravity CLI (`agy`) State Machine & IPC Reference

This reference document provides authoritative mappings and schema specifications extracted from reverse-engineering the `agy` Go binary (`google3/third_party/jetski/cli/*`).

---

## 1. UIPhase Enum (0 ~ 25)

The internal CLI TUI state machine defines 26 `UIPhase` values in `google3/third_party/jetski/cli/store`:

| UIPhase Index | Phase Identifier | Description |
| :---: | :--- | :--- |
| `0` | `AuthStart` | Initiating Google Cloud / OAuth authentication flow |
| `1` | `AuthWaiting` | Waiting for user to complete browser-based verification |
| `2` | `AuthFailure` | Authentication failed or token acquisition error |
| `3` | `SettingsError` | Malformed `settings.json` or syntax/validation error |
| `4` | `Onboarding` | First-run interactive onboarding wizard |
| `5` | `WorkspaceTrust` | Workspace trust prompt before executing actions |
| `6` | `Idle` | Main interactive prompt idle (waiting for user input) |
| `7` | `AgentWorking` | Agent processing turn (LLM thinking, inference, stream generation) |
| `8` | `ToolConfirmation` | Paused waiting for user permission to execute tool |
| `9` | `ReviewAvailable` | File modifications or diffs ready for review |
| `10` | `ArtifactReview` | Reviewing generated markdown artifacts / code blocks |
| `11` | `EditingFeedback` | User editing feedback or modifying suggested turn |
| `12` | `PanelHelp` | `/help` modal panel displayed |
| `13` | `PanelSettings` | `/settings` configuration editor panel |
| `14` | `PanelModelSelector`| `/model` selection panel |
| `15` | `PanelPermissions` | `/permissions` rules manager panel |
| `16` | `PanelSkills` | `/skills` manager panel |
| `17` | `PanelConversationPicker` | `/resume` or `/history` conversation picker |
| `18` | `PanelHooks` | `/hooks` configuration panel |
| `19` | `PanelMcp` | `/mcp` server status and inspection panel |
| `20` | `PanelTasks` | `/tasks` background tasks view |
| `21` | `PanelContext` | `/context` token usage and context item breakdown |
| `22` | `PanelUsage` | `/usage` token stats panel |
| `23` | `PanelCredits` | `/credits` subscription quota and balance panel |
| `24` | `BattleWorking` | Multi-agent battle / competition working state |
| `25` | `BattleIdle` | Multi-agent battle / competition completed/idle |

---

## 2. UIPhase to `agent_state` Jump Table Mapping

In `store.BuildStatusLineData`, an inlined conversion (`uiPhaseToAgentState`) uses an x86-64 jump table (`jmp [rax + rsi*8]` at `0x142bc9e5f` targeting `0x143c58380`):

| `agent_state` Value | Matched `UIPhase` Values | Note |
| :--- | :--- | :--- |
| `"authenticating"` | `AuthStart` (0), `AuthWaiting` (1), `AuthFailure` (2) | Triggered during authentication |
| `"error"` | `SettingsError` (3) | Emitted when configuration fails |
| `"initializing"` | `Onboarding` (4), `WorkspaceTrust` (5), secondary state 0 | Initializing / onboarding workspace |
| `"idle"` | `Idle` (6), Panels (12~23), `BattleIdle` (25), Default fallback | All interactive panels map to `"idle"` |
| `"working"` | `AgentWorking` (7), `BattleWorking` (24), secondary state 1 | **All LLM thinking and generation maps here** |
| `"tool_use"` | `ToolConfirmation` (8) | Waiting for user tool approval |
| `"reviewing"` | `ReviewAvailable` (9), `ArtifactReview` (10), `EditingFeedback` (11) | Artifact or diff review state |
| `"merging"` | Secondary store state (`[rsi+0x38] == 3`) | Branch merge / battle conflict resolution |

> [!IMPORTANT]
> **No `"thinking"` state exists in `agy`**:
> When an agent is thinking or streaming responses, `agy` is in `UIPhase = AgentWorking` (`7`), which maps exclusively to `"working"`. The string `"thinking"` is never emitted by `agy`.

---

## 3. `StatusLineData` JSON Payload Specification

Both `statusLine.command` and `title.command` receive a JSON-serialized `types.StatusLineData` payload piped through standard input:

```json
{
  "agent_state": "working",
  "workspace": {
    "project_dir": "C:/path/to/project",
    "current_dir": "C:/path/to/project"
  },
  "task_count": 2,
  "conversation_id": "ff6b41b3-9825-45d2-a9de-9577a5ad47c9",
  "cycle_mode": "accept_edits",
  "model": {
    "display_name": "Gemini 3.8 Flash (High)",
    "model_name": "gemini-3.8-flash-high"
  },
  "context_window": {
    "total_input_tokens": 102400,
    "max_input_tokens": 1048576,
    "used_percentage": 9.77
  },
  "quota": {
    "gemini-5h": {
      "remaining_fraction": 0.85,
      "reset_time": "2026-09-23T20:00:00Z"
    }
  },
  "terminal_width": 120
}
```
