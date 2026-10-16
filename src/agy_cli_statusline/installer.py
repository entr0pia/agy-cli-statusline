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
DEFAULT_GUI_CONFIG_DIR = Path.home() / ".gemini" / "config"
DEFAULT_GUI_SCRIPTS_DIR = Path.home() / ".gemini" / "antigravity" / "scripts"


def get_agy_dir() -> Path:
    """Get the Antigravity CLI configuration root directory."""
    env_dir = os.environ.get("ANTIGRAVITY_CONFIG_DIR") or os.environ.get("AGY_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return DEFAULT_AGY_DIR


def get_gui_config_dir() -> Path:
    """Get the Antigravity GUI/global configuration directory (~/.gemini/config)."""
    return DEFAULT_GUI_CONFIG_DIR


def is_gui_installed() -> bool:
    """Detect if Antigravity GUI / desktop application is installed."""
    gemini_root = Path.home() / ".gemini"
    gui_indicators = [
        gemini_root / "antigravity",
        gemini_root / "config",
        gemini_root / "antigravity-ide",
    ]
    return any(p.exists() for p in gui_indicators)


def get_target_script_path(agy_dir: Path | None = None) -> Path:
    """Get the target installation path for statusline.py."""
    base = agy_dir or get_agy_dir()
    return base / "scripts" / "statusline.py"


def get_target_title_script_path(agy_dir: Path | None = None) -> Path:
    """Get the target installation path for title.py."""
    base = agy_dir or get_agy_dir()
    return base / "scripts" / "title.py"


def get_target_hook_script_path() -> Path:
    """Get the target installation path for hook_status.py."""
    return DEFAULT_GUI_SCRIPTS_DIR / "hook_status.py"


def get_settings_path(agy_dir: Path | None = None) -> Path:
    """Get the path to settings.json."""
    base = agy_dir or get_agy_dir()
    return base / "settings.json"


def get_hooks_json_path() -> Path:
    """Get the path to ~/.gemini/config/hooks.json."""
    return get_gui_config_dir() / "hooks.json"


def get_python_command(target_script: Path) -> str:
    """Construct the command line string for statusLine/title/hooks in JSON config."""
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


def read_source_title() -> str:
    """Read the bundled title.py source code."""
    try:
        ref = importlib.resources.files("agy_cli_statusline").joinpath("title.py")
        return ref.read_text(encoding="utf-8")
    except Exception:
        fallback = Path(__file__).parent / "title.py"
        return fallback.read_text(encoding="utf-8")


def read_source_hook() -> str:
    """Read the bundled hook_status.py source code."""
    try:
        ref = importlib.resources.files("agy_cli_statusline").joinpath("hook_status.py")
        return ref.read_text(encoding="utf-8")
    except Exception:
        fallback = Path(__file__).parent / "hook_status.py"
        return fallback.read_text(encoding="utf-8")


def install(agy_dir: Path | None = None, dry_run: bool = False, debug: bool | None = None) -> bool:
    """Install statusline and title scripts and initialize settings.json configuration."""
    base = agy_dir or get_agy_dir()
    target_statusline = get_target_script_path(base)
    target_title = get_target_title_script_path(base)
    settings_file = get_settings_path(base)

    print(f"[*] Target Antigravity CLI directory: {base}")

    # 1. Place script files
    statusline_content = read_source_statusline()
    title_content = read_source_title()
    if dry_run:
        print(f"[dry-run] Would write statusline script to: {target_statusline}")
        print(f"[dry-run] Would write title script to: {target_title}")
    else:
        target_statusline.parent.mkdir(parents=True, exist_ok=True)
        target_statusline.write_text(statusline_content, encoding="utf-8")
        print(f"[✓] Statusline script placed: {target_statusline}")

        target_title.parent.mkdir(parents=True, exist_ok=True)
        target_title.write_text(title_content, encoding="utf-8")
        print(f"[✓] Title script placed: {target_title}")

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

    statusline_command = get_python_command(target_statusline)
    status_line_config = {
        "type": "command",
        "command": statusline_command,
        "enabled": True,
        "debug": debug_val,
    }
    if isinstance(existing_statusline, dict):
        for k in ("themeColor", "color"):
            if k in existing_statusline:
                status_line_config[k] = existing_statusline[k]
    settings["statusLine"] = status_line_config

    title_command = get_python_command(target_title)
    title_config = {
        "type": "command",
        "command": title_command,
        "enabled": True,
    }
    settings["title"] = title_config

    if dry_run:
        print(f"[dry-run] Would update {settings_file} statusLine: {status_line_config}")
        print(f"[dry-run] Would update {settings_file} title: {title_config}")
    else:
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"[✓] Configuration updated: {settings_file}")
        print(f"    statusLine.command: {statusline_command}")
        print(f"    title.command:      {title_command}")

    # 3. Detect and configure GUI Hook (if GUI environment detected)
    gui_present = is_gui_installed()
    if gui_present:
        target_hook = get_target_hook_script_path()
        hooks_file = get_hooks_json_path()
        hook_content = read_source_hook()

        print(f"\n[*] Antigravity GUI detected. Configuring PostInvocation hook...")
        if dry_run:
            print(f"[dry-run] Would write hook script to: {target_hook}")
        else:
            target_hook.parent.mkdir(parents=True, exist_ok=True)
            target_hook.write_text(hook_content, encoding="utf-8")
            print(f"[✓] Hook script placed: {target_hook}")

        # Update ~/.gemini/config/hooks.json
        hooks_data: dict = {}
        if hooks_file.exists():
            try:
                with open(hooks_file, "r", encoding="utf-8") as f:
                    hooks_data = json.load(f)
            except Exception as e:
                print(f"[!] Failed to parse existing hooks.json ({e}), creating backup...")
                if not dry_run:
                    bak = hooks_file.with_suffix(".json.bak")
                    shutil.copy2(hooks_file, bak)
                    print(f"[✓] Backup created at: {bak}")
                hooks_data = {}

        hook_command = get_python_command(target_hook)
        hooks_data["context-status-appender"] = {
            "enabled": True,
            "PostInvocation": [
                {
                    "type": "command",
                    "command": hook_command,
                    "timeout": 10,
                }
            ],
        }

        if dry_run:
            print(f"[dry-run] Would update {hooks_file}: context-status-appender -> {hook_command}")
        else:
            hooks_file.parent.mkdir(parents=True, exist_ok=True)
            with open(hooks_file, "w", encoding="utf-8") as f:
                json.dump(hooks_data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            print(f"[✓] GUI Hooks updated: {hooks_file}")
            print(f"    context-status-appender: {hook_command}")
    else:
        print("\n[-] Antigravity GUI environment not detected, skipping GUI hook setup.")

    print("\n🎉 Installation completed successfully! Restart agy or GUI to take effect.")
    return True


def uninstall(
    agy_dir: Path | None = None,
    remove_script: bool = True,
    dry_run: bool = False,
    include_gui: bool = True,
) -> bool:
    """Remove statusline, title, and GUI hook configuration and scripts."""
    base = agy_dir or get_agy_dir()
    target_statusline = get_target_script_path(base)
    target_title = get_target_title_script_path(base)
    settings_file = get_settings_path(base)

    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
            updated = False
            if "statusLine" in settings:
                if dry_run:
                    print(f"[dry-run] Would remove statusLine configuration from {settings_file}")
                else:
                    del settings["statusLine"]
                    print(f"[✓] Removed statusLine configuration from {settings_file}")
                updated = True
            else:
                print(f"[-] No statusLine configuration found in {settings_file}")

            if "title" in settings:
                if dry_run:
                    print(f"[dry-run] Would remove title configuration from {settings_file}")
                else:
                    del settings["title"]
                    print(f"[✓] Removed title configuration from {settings_file}")
                updated = True
            else:
                print(f"[-] No title configuration found in {settings_file}")

            if updated and not dry_run:
                with open(settings_file, "w", encoding="utf-8") as f:
                    json.dump(settings, f, indent=2, ensure_ascii=False)
                    f.write("\n")
        except Exception as e:
            print(f"[!] Failed to update settings.json: {e}")

    # Remove GUI hook if requested
    if include_gui:
        hooks_file = get_hooks_json_path()
        target_hook = get_target_hook_script_path()

        if hooks_file.exists():
            try:
                with open(hooks_file, "r", encoding="utf-8") as f:
                    hooks_data = json.load(f)
                if "context-status-appender" in hooks_data:
                    if dry_run:
                        print(f"[dry-run] Would remove context-status-appender from {hooks_file}")
                    else:
                        del hooks_data["context-status-appender"]
                        with open(hooks_file, "w", encoding="utf-8") as f:
                            json.dump(hooks_data, f, indent=2, ensure_ascii=False)
                            f.write("\n")
                        print(f"[✓] Removed context-status-appender from {hooks_file}")
            except Exception as e:
                print(f"[!] Failed to update hooks.json: {e}")

        if remove_script and target_hook.exists():
            if dry_run:
                print(f"[dry-run] Would delete hook script: {target_hook}")
            else:
                target_hook.unlink(missing_ok=True)
                print(f"[✓] Hook script removed: {target_hook}")

    if remove_script:
        for script_path in [target_statusline, target_title]:
            if script_path.exists():
                if dry_run:
                    print(f"[dry-run] Would delete script: {script_path}")
                else:
                    script_path.unlink(missing_ok=True)
                    print(f"[✓] Script removed: {script_path}")

    print("\n[✓] Uninstall completed.")
    return True


def status(agy_dir: Path | None = None) -> None:
    """Check current statusline, title, and GUI hook installation and configuration status."""
    base = agy_dir or get_agy_dir()
    target_statusline = get_target_script_path(base)
    target_title = get_target_title_script_path(base)
    settings_file = get_settings_path(base)

    print("=== Antigravity CLI (agy) ===")
    print(f"Config Directory:  {base}")
    print(f"Statusline script: {target_statusline} -> {'[Installed]' if target_statusline.exists() else '[Not Installed]'}")
    print(f"Title script:      {target_title} -> {'[Installed]' if target_title.exists() else '[Not Installed]'}")
    print(f"Settings file:     {settings_file} -> {'[Exists]' if settings_file.exists() else '[Not Found]'}")

    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
            cfg = settings.get("statusLine")
            if cfg:
                print(f"Current statusLine:\n{json.dumps(cfg, indent=2, ensure_ascii=False)}")
            else:
                print("statusLine is not configured in settings.json")

            t_cfg = settings.get("title")
            if t_cfg:
                print(f"Current title:\n{json.dumps(t_cfg, indent=2, ensure_ascii=False)}")
            else:
                print("title is not configured in settings.json")
        except Exception as e:
            print(f"Failed to read settings.json: {e}")

    print("\n=== Antigravity GUI (Desktop) ===")
    gui_present = is_gui_installed()
    print(f"GUI Detected:      {'Yes' if gui_present else 'No'}")
    target_hook = get_target_hook_script_path()
    hooks_file = get_hooks_json_path()
    print(f"Hook script:       {target_hook} -> {'[Installed]' if target_hook.exists() else '[Not Installed]'}")
    print(f"Hooks file:        {hooks_file} -> {'[Exists]' if hooks_file.exists() else '[Not Found]'}")

    if hooks_file.exists():
        try:
            with open(hooks_file, "r", encoding="utf-8") as f:
                hooks_data = json.load(f)
            hook_entry = hooks_data.get("context-status-appender")
            if hook_entry:
                print(f"Current GUI hook:\n{json.dumps(hook_entry, indent=2, ensure_ascii=False)}")
            else:
                print("context-status-appender is not configured in hooks.json")
        except Exception as e:
            print(f"Failed to read hooks.json: {e}")


def cli_main() -> None:
    parser = argparse.ArgumentParser(
        prog="agy-cli-statusline",
        description="One-click installer and statusline/title/GUI-hook manager for Google Antigravity",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands (default: install)")

    # install subcommand
    install_parser = subparsers.add_parser(
        "install",
        help="Install statusline, title, and GUI hook scripts and update configuration (default)",
    )
    install_parser.add_argument("--dry-run", action="store_true", help="Dry run without modifying files")
    install_parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable debug recording of statusline payload (default: False)",
    )

    # uninstall subcommand
    uninstall_parser = subparsers.add_parser(
        "uninstall",
        help="Remove statusline, title, and GUI hook configuration and scripts",
    )
    uninstall_parser.add_argument("--keep-script", action="store_true", help="Keep script files and only remove settings")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="Dry run without modifying files")

    # status subcommand
    subparsers.add_parser("status", help="Check statusline, title, and GUI hook status")

    # Root flags
    parser.add_argument("--dry-run", action="store_true", help="Dry run without modifying files")
    parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable debug recording of statusline payload (default: False)",
    )
    parser.add_argument("--status", action="store_true", help="Check statusline, title, and GUI hook status")
    parser.add_argument("--uninstall", action="store_true", help="Remove statusline, title, and GUI hook configuration")

    args = parser.parse_args()

    if args.status or args.command == "status":
        status()
    elif args.uninstall or args.command == "uninstall":
        keep_script = getattr(args, "keep_script", False)
        uninstall(remove_script=not keep_script, dry_run=args.dry_run)
    else:
        install(dry_run=args.dry_run, debug=args.debug)

