# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import importlib.resources
import json
import os
import shutil
import sys
from pathlib import Path

# Ensure UTF-8 I/O on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_AGY_DIR = Path.home() / ".gemini" / "antigravity-cli"



def get_agy_dir() -> Path:
    """Get the Antigravity CLI configuration root directory."""
    env_dir = os.environ.get("ANTIGRAVITY_CONFIG_DIR") or os.environ.get("AGY_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return DEFAULT_AGY_DIR


def get_target_script_path(agy_dir: Path | None = None) -> Path:
    """Get the target installation path for statusline.py."""
    base = agy_dir or get_agy_dir()
    return base / "scripts" / "statusline.py"


def get_settings_path(agy_dir: Path | None = None) -> Path:
    """Get the path to settings.json."""
    base = agy_dir or get_agy_dir()
    return base / "settings.json"


def get_python_command(target_script: Path) -> str:
    """Construct the command line string for statusLine in settings.json."""
    script_posix = target_script.as_posix()
    quoted_path = f'"{script_posix}"' if " " in script_posix else script_posix
    py_cmd = "python"
    if sys.platform != "win32" and not shutil.which("python") and shutil.which("python3"):
        py_cmd = "python3"
    return f"{py_cmd} {quoted_path}"


def read_source_statusline() -> str:
    """Read the bundled statusline.py source code."""
    try:
        ref = importlib.resources.files("agy_cli_statusline").joinpath("statusline.py")
        return ref.read_text(encoding="utf-8")
    except Exception:
        fallback = Path(__file__).parent / "statusline.py"
        return fallback.read_text(encoding="utf-8")


def install(agy_dir: Path | None = None, dry_run: bool = False, debug: bool | None = None) -> bool:
    """Install statusline script and initialize settings.json configuration."""
    base = agy_dir or get_agy_dir()
    target_script = get_target_script_path(base)
    settings_file = get_settings_path(base)

    print(f"[*] Target Antigravity CLI directory: {base}")

    # 1. Place script file
    content = read_source_statusline()
    if dry_run:
        print(f"[dry-run] Would write script to: {target_script}")
    else:
        target_script.parent.mkdir(parents=True, exist_ok=True)
        target_script.write_text(content, encoding="utf-8")
        print(f"[✓] Script placed: {target_script}")

    # 2. Update settings.json
    settings: dict = {}
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception as e:
            print(f"[!] Failed to parse existing settings.json ({e}), creating backup...")
            if not dry_run:
                bak = settings_file.with_suffix(".json.bak")
                shutil.copy2(settings_file, bak)
                print(f"[✓] Backup created at: {bak}")
            settings = {}

    existing_statusline = settings.get("statusLine", {})
    if debug is not None:
        debug_val = debug
    elif isinstance(existing_statusline, dict) and "debug" in existing_statusline:
        debug_val = bool(existing_statusline["debug"])
    else:
        debug_val = False

    command = get_python_command(target_script)
    status_line_config = {
        "type": "command",
        "command": command,
        "enabled": True,
        "debug": debug_val,
    }

    settings["statusLine"] = status_line_config

    if dry_run:
        print(f"[dry-run] Would update {settings_file} statusLine: {status_line_config}")
    else:
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"[✓] Configuration updated: {settings_file}")
        print(f"    statusLine.command: {command}")

    print("\n🎉 agy-cli-statusline successfully installed and configured! Restart agy to take effect.")
    return True


def uninstall(agy_dir: Path | None = None, remove_script: bool = True, dry_run: bool = False) -> bool:
    """Remove statusline configuration and script."""
    base = agy_dir or get_agy_dir()
    target_script = get_target_script_path(base)
    settings_file = get_settings_path(base)

    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
            if "statusLine" in settings:
                if dry_run:
                    print(f"[dry-run] Would remove statusLine configuration from {settings_file}")
                else:
                    del settings["statusLine"]
                    with open(settings_file, "w", encoding="utf-8") as f:
                        json.dump(settings, f, indent=2, ensure_ascii=False)
                        f.write("\n")
                    print(f"[✓] Removed statusLine configuration from {settings_file}")
            else:
                print(f"[-] No statusLine configuration found in {settings_file}")
        except Exception as e:
            print(f"[!] Failed to update settings.json: {e}")

    if remove_script and target_script.exists():
        if dry_run:
            print(f"[dry-run] Would delete script: {target_script}")
        else:
            target_script.unlink(missing_ok=True)
            print(f"[✓] Script removed: {target_script}")

    print("\n[✓] Uninstall completed.")
    return True


def status(agy_dir: Path | None = None) -> None:
    """Check current statusline installation and configuration status."""
    base = agy_dir or get_agy_dir()
    target_script = get_target_script_path(base)
    settings_file = get_settings_path(base)

    print(f"Antigravity CLI directory: {base}")
    print(f"Script file: {target_script} -> {'[Installed]' if target_script.exists() else '[Not Installed]'}")
    print(f"Settings file: {settings_file} -> {'[Exists]' if settings_file.exists() else '[Not Found]'}")

    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
            cfg = settings.get("statusLine")
            if cfg:
                print(f"Current statusLine configuration:\n{json.dumps(cfg, indent=2, ensure_ascii=False)}")
            else:
                print("statusLine is not configured in settings.json")
        except Exception as e:
            print(f"Failed to read settings.json: {e}")


def cli_main() -> None:
    parser = argparse.ArgumentParser(
        prog="agy-cli-statusline",
        description="One-click installer and statusline manager for Google Antigravity CLI (agy)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands (default: install)")

    # install subcommand
    install_parser = subparsers.add_parser("install", help="Install statusline script and update configuration (default)")
    install_parser.add_argument("--dry-run", action="store_true", help="Dry run without modifying files")
    install_parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable debug recording of statusline payload (default: False)",
    )

    # uninstall subcommand
    uninstall_parser = subparsers.add_parser("uninstall", help="Remove statusline configuration and script")
    uninstall_parser.add_argument("--keep-script", action="store_true", help="Keep script file and only remove settings")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="Dry run without modifying files")

    # status subcommand
    subparsers.add_parser("status", help="Check statusline installation and configuration status")

    # Root flags
    parser.add_argument("--dry-run", action="store_true", help="Dry run without modifying files")
    parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable debug recording of statusline payload (default: False)",
    )
    parser.add_argument("--status", action="store_true", help="Check statusline installation and configuration status")
    parser.add_argument("--uninstall", action="store_true", help="Remove statusline configuration and script")

    args = parser.parse_args()

    if args.status or args.command == "status":
        status()
    elif args.uninstall or args.command == "uninstall":
        keep_script = getattr(args, "keep_script", False)
        uninstall(remove_script=not keep_script, dry_run=args.dry_run)
    else:
        install(dry_run=args.dry_run, debug=args.debug)

