#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dump_jump_table.py

Dump and decode x86-64 switch jump tables (e.g. jmp qword ptr [rax + rsi*8]) from agy.exe,
extracting loaded string pointers, string lengths, and literal values for each enum index.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import struct
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from parse_go_pclntab import GoPEParser, default_agy_path
except ImportError:
    from .parse_go_pclntab import GoPEParser, default_agy_path


def decode_jump_table(
    exe_path: str,
    table_va_str: str,
    count: int = 26,
    labels: list[str] | None = None,
) -> None:
    parser = GoPEParser(exe_path)
    table_va = int(table_va_str, 16) if table_va_str.startswith("0x") else int(table_va_str)

    table_fo = parser.va_to_file_offset(table_va)
    if table_fo is None:
        print(f"[!] Invalid table VA 0x{table_va:x}: not mapped to file offset.")
        return

    print(f"[*] Reading jump table at VA 0x{table_va:x} (File offset: 0x{table_fo:x}), {count} entries:")

    content = parser.content
    targets: list[int] = []
    for i in range(count):
        target = struct.unpack_from("<Q", content, table_fo + i * 8)[0]
        targets.append(target)

    for idx, target_va in enumerate(targets):
        label = labels[idx] if labels and idx < len(labels) else f"Case {idx}"
        target_fo = parser.va_to_file_offset(target_va)
        if target_fo is None:
            print(f"  [{idx:2d}] {label:24s} -> Invalid target 0x{target_va:x}")
            continue

        # Read first 30 bytes of target code
        code = content[target_fo : target_fo + 30]

        str_len = None
        str_ptr = None

        # Pattern:
        # b8 len 00 00 00 (mov eax, imm32) -> len
        # 48 8d 0d disp32 / 48 8d 15 disp32 (lea rcx/rdx, [rip + disp32]) -> str_ptr
        if code[0] == 0xB8:
            str_len = struct.unpack_from("<I", code, 1)[0]
        elif code[0] == 0xBE:
            str_len = struct.unpack_from("<I", code, 1)[0]

        i = 0
        while i < len(code) - 7:
            b0, b1, b2 = code[i], code[i + 1], code[i + 2]
            if (b0 & 0xF8) == 0x48 and b1 == 0x8D and (b2 & 0xC7) == 0x05:
                disp = struct.unpack_from("<i", code, i + 3)[0]
                str_ptr = target_va + i + 7 + disp
                break
            i += 1

        val = "<unknown>"
        if str_ptr:
            length = str_len if str_len is not None else 16
            str_fo = parser.va_to_file_offset(str_ptr)
            if str_fo is not None and 0 <= str_fo < len(content):
                val = content[str_fo : str_fo + length].decode("utf-8", errors="replace")

        print(f"  [{idx:2d}] {label:24s} -> Target 0x{target_va:x} | len={str_len if str_len is not None else '?':2} => {val!r}")


# Known UIPhase labels in agy
DEFAULT_AGY_UIPHASE_LABELS = [
    "AuthStart",
    "AuthWaiting",
    "AuthFailure",
    "SettingsError",
    "Onboarding",
    "WorkspaceTrust",
    "Idle",
    "AgentWorking",
    "ToolConfirmation",
    "ReviewAvailable",
    "ArtifactReview",
    "EditingFeedback",
    "PanelHelp",
    "PanelSettings",
    "PanelModelSelector",
    "PanelPermissions",
    "PanelSkills",
    "PanelConversationPicker",
    "PanelHooks",
    "PanelMcp",
    "PanelTasks",
    "PanelContext",
    "PanelUsage",
    "PanelCredits",
    "BattleWorking",
    "BattleIdle",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Decode x86-64 switch jump table and string outputs in agy.exe")
    parser.add_argument("--va", default="0x143c58380", help="Virtual Address of jump table (default: agy UIPhase jump table 0x143c58380)")
    parser.add_argument("--count", type=int, default=26, help="Number of table entries (default: 26)")
    parser.add_argument("--exe", default=default_agy_path(), help="Path to Go executable")

    args = parser.parse_args()

    if not Path(args.exe).exists():
        print(f"[!] Executable not found: {args.exe}")
        sys.exit(1)

    labels = DEFAULT_AGY_UIPHASE_LABELS if args.count == len(DEFAULT_AGY_UIPHASE_LABELS) else None
    decode_jump_table(args.exe, args.va, count=args.count, labels=labels)


if __name__ == "__main__":
    main()
