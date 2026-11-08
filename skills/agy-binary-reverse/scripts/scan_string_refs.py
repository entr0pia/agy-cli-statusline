#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_string_refs.py

Search for target string/bytes in a PE binary (like agy.exe), calculate its Virtual Address (VA),
and scan the .text section for RIP-relative LEA instructions (e.g. 48 8d / 4c 8d) referencing it.
Automatically maps referencing instructions back to their containing Go function names.
"""

from __future__ import annotations

import argparse
import os
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


def scan_string_references(exe_path: str, search_text: str, max_refs: int = 20) -> None:
    parser = GoPEParser(exe_path)
    content = parser.content
    search_bytes = search_text.encode("utf-8")

    # 1. Locate string occurrence in binary
    pos = 0
    string_locations: list[int] = []
    while True:
        pos = content.find(search_bytes, pos)
        if pos == -1:
            break
        string_locations.append(pos)
        pos += len(search_bytes)

    if not string_locations:
        print(f"[-] String not found in binary: {search_text!r}")
        return

    print(f"[+] Found {len(string_locations)} occurrence(s) of string {search_text!r}:")
    for fo in string_locations[:5]:
        va = parser.file_offset_to_va(fo)
        va_str = f"0x{va:x}" if va else "unknown"
        print(f"    File offset: 0x{fo:x} -> VA: {va_str}")

    target_va = parser.file_offset_to_va(string_locations[0])
    if not target_va:
        print("[!] Target string is not located inside any mapped PE section.")
        return

    # 2. Locate .text section
    text_sec = None
    for s in parser.sections:
        if s["name"] == ".text":
            text_sec = s
            break

    if not text_sec:
        print("[!] Could not find .text section.")
        return

    text_raw_start = text_sec["raw_offset"]
    text_raw_size = text_sec["raw_size"]
    text_va_base = parser.image_base + text_sec["va"]
    text_bytes = content[text_raw_start : text_raw_start + text_raw_size]

    print(f"\n[*] Scanning .text section (VA 0x{text_va_base:x} - 0x{text_va_base + text_raw_size:x}) for RIP-relative LEA...")

    # LEA reg, [rip + disp32]
    # Opcode format: 48 8d / 4c 8d with ModR/M == 0x05 / 0x0d / 0x15 / 0x1d / 0x25 / 0x2d / 0x35 / 0x3d
    # Instruction length is 7 bytes
    matches: list[tuple[int, int]] = []
    for i in range(len(text_bytes) - 7):
        b0 = text_bytes[i]
        b1 = text_bytes[i + 1]
        b2 = text_bytes[i + 2]
        if (b0 & 0xF8) == 0x48 and b1 == 0x8D and (b2 & 0xC7) == 0x05:
            disp = struct.unpack_from("<i", text_bytes, i + 3)[0]
            insn_va = text_va_base + i
            dest_va = insn_va + 7 + disp
            if dest_va == target_va:
                matches.append((insn_va, text_raw_start + i))
                if len(matches) >= max_refs:
                    break

    print(f"[✓] Found {len(matches)} LEA reference(s):")
    for insn_va, file_off in matches:
        func_name, func_start = parser.lookup_func_by_va(insn_va)
        print(f"\n  • Instruction VA: 0x{insn_va:x} (File offset: 0x{file_off:x})")
        print(f"    Function:       {func_name}")
        if func_start:
            offset_in_func = insn_va - func_start
            print(f"    Func Start:     0x{func_start:x} (+0x{offset_in_func:x})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan PE binary for RIP-relative LEA references to string literals")
    parser.add_argument("string", help="String literal to search for")
    parser.add_argument("--exe", default=default_agy_path(), help="Path to Go executable")
    parser.add_argument("--limit", type=int, default=20, help="Max references to report")

    args = parser.parse_args()

    if not Path(args.exe).exists():
        print(f"[!] Executable not found: {args.exe}")
        sys.exit(1)

    scan_string_references(args.exe, args.string, max_refs=args.limit)


if __name__ == "__main__":
    main()
