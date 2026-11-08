---
name: agy-binary-reverse
description: Reverse-engineer and inspect Google Antigravity CLI (agy) binary internals. Use when needing to verify undocumented agent states, inspect statusline or title JSON IPC payloads, trace Go runtime pclntab symbols, scan string cross-references, or analyze switch jump tables in agy.exe.
---

# Antigravity CLI (`agy`) Binary Reverse-Engineering

This skill provides a systematic workflow and automated tooling to reverse-engineer and inspect the **Google Antigravity CLI (`agy.exe`)** executable.

The `agy` CLI is a Go-compiled 64-bit PE console binary (located at `%LOCALAPPDATA%\agy\bin\agy.exe`). Even without source code or debug symbols, its internal Go metadata (`pclntab`), jump tables, and string references can be recovered completely using pure Python without external dependencies.

---

## Quick Reference Tools

All helper scripts are located in [`scripts/`](scripts/) and require only Python 3.10+ standard library:

| Script | Purpose | Example Usage |
| :--- | :--- | :--- |
| [`parse_go_pclntab.py`](scripts/parse_go_pclntab.py) | Recover 170,000+ Go function symbols & VAs | `uv run python skills/agy-binary-reverse/scripts/parse_go_pclntab.py --filter "StatusLine"` |
| [`scan_string_refs.py`](scripts/scan_string_refs.py) | Find RIP-relative `LEA` xrefs to any string | `uv run python skills/agy-binary-reverse/scripts/scan_string_refs.py "No title command configured"` |
| [`dump_jump_table.py`](scripts/dump_jump_table.py) | Decode x86-64 switch jump tables & state strings | `uv run python skills/agy-binary-reverse/scripts/dump_jump_table.py` |

---

## 5-Step Binary Reverse-Engineering Playbook

### Step 1: Binary Identification & PE Sections

Locate the binary and determine its PE header layout:

```powershell
which agy
# Output: C:\Users\<Username>\AppData\Local\agy\bin\agy.EXE
```

The binary contains standard PE sections:
- `.text`: Machine code instructions (entry point ~ `0x140001000`)
- `.rdata`: Read-only data containing string tables, Go `pclntab`, and switch jump tables
- `.data`: Mutable global variables and type descriptors

### Step 2: Symbol Recovery via Go `pclntab`

Go binaries retain full function names and PC address ranges inside the program counter line table (`pclntab`) even when stripped.

1. Locate the Go 1.20+ magic header: `0xfffffff1` in `.rdata`.
2. Parse `nfunc`, `funcnametab_off`, and `pcln_tab_off`.
3. Search for functions in the target component:

```powershell
uv run python skills/agy-binary-reverse/scripts/parse_go_pclntab.py --filter "triggerTitleUpdate"
# Finds: 0x142be0b00 : google3/third_party/jetski/cli/store/store.(*Manager).triggerTitleUpdate
```

### Step 3: Anchor String & Cross-Reference Tracing

When investigating user-facing behaviors (e.g. error messages, prompts, or configuration warnings), search for the string literal and trace referencing code:

```powershell
uv run python skills/agy-binary-reverse/scripts/scan_string_refs.py "Error: No title command configured in settings.json"
```

*Output:*
```text
[✓] Found 1 LEA reference(s):
  • Instruction VA: 0x142c343ae (File offset: 0x2c339ae)
    Function:       google3/third_party/jetski/cli/commands/commands.(*titleCommand).Execute.func1
    Func Start:     0x142c33ea0 (+0x50e)
```

This immediately pinpoints the command execution logic in the CLI codebase.

### Step 4: State Machine & Jump Table Decoding

Many state translations in Go are implemented as `switch` statements compiled into contiguous 64-bit jump tables (`jmp qword ptr [rax + rsi*8]`):

1. Identify the jump table VA in `.rdata` (e.g., loaded via `lea rax, [rip+disp32]`).
2. Run [`dump_jump_table.py`](scripts/dump_jump_table.py) to extract all targets, string lengths, and string constants:

```powershell
uv run python skills/agy-binary-reverse/scripts/dump_jump_table.py --va 0x143c58380 --count 26
```

*Output:*
```text
  [ 6] Idle                 -> Target 0x142bc9e91 | len= 4 => 'idle'
  [ 7] AgentWorking         -> Target 0x142bc9e9f | len= 7 => 'working'
  [ 8] ToolConfirmation     -> Target 0x142bc9ead | len= 8 => 'tool_use'
  [ 9] ReviewAvailable      -> Target 0x142bc9ebb | len= 9 => 'reviewing'
```

For the complete list of all 26 UI phases and their mappings, see [`references/state_machine_reference.md`](references/state_machine_reference.md).

### Step 5: JSON IPC Payload Reconstruction

`agy` communicates with external scripts via standard input JSON payloads:

1. Locate the data builder function using symbol search:
   `store.BuildStatusLineData` (at `0x142bc93e0`).
2. Inspect the fields of `types.StatusLineData`.
3. Verify that both `statusLine` and `title` hooks execute through the shared runner `StatusLineRunner`.

See [`references/agy_internals.md`](references/agy_internals.md) for details on `StatusLineRunner` execution and IPC piping.

---

## Detailed References

- [State Machine & IPC Reference](references/state_machine_reference.md): Complete `UIPhase` (0~25) enum table and `agent_state` mappings.
- [CLI Internal Modules & Architecture](references/agy_internals.md): Overview of `google3/third_party/jetski/cli/*` package structure and execution model.
