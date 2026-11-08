#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_go_pclntab.py

Parse Go 1.18+ pclntab (program counter line table) from a Go PE binary (e.g. agy.exe),
recovering function names, addresses, and symbol mappings without requiring external disassemblers.
"""

from __future__ import annotations

import argparse
import bisect
import os
from pathlib import Path
import struct
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def default_agy_path() -> str:
    local_app_data = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    candidate = Path(local_app_data) / "agy" / "bin" / "agy.exe"
    if candidate.exists():
        return str(candidate)
    return "agy.exe"


class GoPEParser:
    def __init__(self, file_path: str):
        self.path = file_path
        with open(file_path, "rb") as f:
            self.content = f.read()
        self._parse_pe()
        self._locate_pclntab()

    def _parse_pe(self) -> None:
        e_lfanew = struct.unpack_from("<I", self.content, 0x3C)[0]
        num_sections = struct.unpack_from("<H", self.content, e_lfanew + 6)[0]
        opt_hdr_size = struct.unpack_from("<H", self.content, e_lfanew + 20)[0]
        opt_hdr_offset = e_lfanew + 24
        self.image_base = struct.unpack_from("<Q", self.content, opt_hdr_offset + 24)[0]

        self.sections = []
        sec_table_offset = opt_hdr_offset + opt_hdr_size
        for i in range(num_sections):
            sec = self.content[sec_table_offset + i * 40 : sec_table_offset + (i + 1) * 40]
            name = sec[:8].rstrip(b"\x00").decode("latin1")
            vsize, va, raw_size, raw_offset = struct.unpack_from("<IIII", sec, 8)
            self.sections.append({
                "name": name,
                "va": va,
                "vsize": vsize,
                "raw_offset": raw_offset,
                "raw_size": raw_size,
            })

    def rva_to_va(self, rva: int) -> int:
        return self.image_base + rva

    def file_offset_to_va(self, offset: int) -> int | None:
        for s in self.sections:
            if s["raw_offset"] <= offset < s["raw_offset"] + s["raw_size"]:
                return self.image_base + s["va"] + (offset - s["raw_offset"])
        return None

    def va_to_file_offset(self, va: int) -> int | None:
        rva = va - self.image_base
        for s in self.sections:
            if s["va"] <= rva < s["va"] + s["vsize"]:
                return s["raw_offset"] + (rva - s["va"])
        return None

    def _locate_pclntab(self) -> None:
        # Go pclntab magic headers (Go 1.18 - 1.22+)
        magics = [
            b"\xf1\xff\xff\xff\x00\x00",
            b"\xf0\xff\xff\xff\x00\x00",
            b"\xfb\xff\xff\xff\x00\x00",
            b"\xfa\xff\xff\xff\x00\x00",
        ]
        self.pcln_offset = None
        for m in magics:
            idx = self.content.find(m)
            if idx != -1:
                # Check valid pointer size and quantum
                min_lc = self.content[idx + 6]
                ptr_size = self.content[idx + 7]
                if ptr_size == 8:
                    self.pcln_offset = idx
                    self.magic = m
                    break

        if self.pcln_offset is None:
            raise ValueError("Failed to locate valid Go pclntab magic header in binary.")

        # Read Go 1.18+ pcln header:
        # uint32 magic, uint8 pad1, pad2, minLC, ptrSize (8)
        # uintptr nfunc (8)
        # uintptr nfiles (8)
        # uintptr textStart (8)
        # uintptr funcnameOffset (8)
        # uintptr cuOffset (8)
        # uintptr filetabOffset (8)
        # uintptr pctabOffset (8)
        # uintptr pclnOffset (8)
        self.nfunc = struct.unpack_from("<Q", self.content, self.pcln_offset + 8)[0]
        self.funcnametab_off = self.pcln_offset + struct.unpack_from("<Q", self.content, self.pcln_offset + 32)[0]
        self.pcln_tab_off = self.pcln_offset + struct.unpack_from("<Q", self.content, self.pcln_offset + 64)[0]

        # Cache function PC list for binary search
        self.func_pcs: list[int] = []
        self.func_entry_offs: list[int] = []
        self.func_name_offs: list[int] = []

        text_base = 0x140001000
        for s in self.sections:
            if s["name"] == ".text":
                text_base = self.image_base + s["va"]
                break

        for i in range(self.nfunc):
            pc_off = struct.unpack_from("<I", self.content, self.pcln_tab_off + i * 8)[0]
            fn_off = struct.unpack_from("<I", self.content, self.pcln_tab_off + i * 8 + 4)[0]
            func_ptr = self.pcln_tab_off + fn_off
            entry_off = struct.unpack_from("<I", self.content, func_ptr)[0]
            name_off = struct.unpack_from("<i", self.content, func_ptr + 4)[0]

            self.func_pcs.append(text_base + pc_off)
            self.func_entry_offs.append(entry_off)
            self.func_name_offs.append(name_off)

    def lookup_func_by_va(self, va: int) -> tuple[str | None, int | None]:
        idx = bisect.bisect_right(self.func_pcs, va) - 1
        if idx < 0 or idx >= len(self.func_pcs):
            return None, None
        name_off = self.func_name_offs[idx]
        name_bytes = self.content[self.funcnametab_off + name_off : self.funcnametab_off + name_off + 250]
        name = name_bytes.split(b"\x00")[0].decode("ascii", errors="replace")
        func_start_va = self.func_pcs[idx]
        return name, func_start_va

    def search_functions(self, pattern: str) -> list[tuple[str, int]]:
        results: list[tuple[str, int]] = []
        pat_lower = pattern.lower()
        for i in range(self.nfunc):
            name_off = self.func_name_offs[i]
            name_bytes = self.content[self.funcnametab_off + name_off : self.funcnametab_off + name_off + 250]
            name = name_bytes.split(b"\x00")[0].decode("ascii", errors="replace")
            if pat_lower in name.lower():
                results.append((name, self.func_pcs[i]))
        return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Go pclntab parser for agy and Go PE binaries")
    parser.add_argument("--exe", default=default_agy_path(), help="Path to Go executable")
    parser.add_argument("--filter", "-f", default=None, help="Filter functions containing substring")
    parser.add_argument("--lookup", "-l", default=None, help="Lookup function by hex Virtual Address (e.g. 0x142bc93e0)")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of matches to display (default: 50)")

    args = parser.parse_args()

    if not Path(args.exe).exists():
        print(f"[!] Executable not found: {args.exe}")
        sys.exit(1)

    print(f"[*] Parsing Go pclntab from: {args.exe}")
    parser_obj = GoPEParser(args.exe)
    print(f"[✓] ImageBase: 0x{parser_obj.image_base:x}, Functions: {parser_obj.nfunc:,}")

    if args.lookup:
        va = int(args.lookup, 16) if args.lookup.startswith("0x") else int(args.lookup)
        name, start_va = parser_obj.lookup_func_by_va(va)
        print(f"\n[+] Lookup 0x{va:x}:")
        print(f"    Function Name:  {name}")
        print(f"    Function Start: 0x{start_va:x}" if start_va else "    Function Start: unknown")
        return

    if args.filter:
        matches = parser_obj.search_functions(args.filter)
        print(f"\n[+] Found {len(matches)} matching function(s) for '{args.filter}':")
        for name, va in matches[: args.limit]:
            print(f"    0x{va:x} : {name}")
        if len(matches) > args.limit:
            print(f"    ... and {len(matches) - args.limit} more (use --limit to see more)")
    else:
        print("\nTip: Use --filter <keyword> to search symbols, or --lookup <0xVA> to resolve an address.")


if __name__ == "__main__":
    main()
