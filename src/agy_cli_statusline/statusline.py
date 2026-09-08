# -*- coding: utf-8 -*-
import sys
import os
import json
import re
import ctypes
import struct
import unicodedata
from pathlib import Path

# Ensure UTF-8 I/O on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

# ANSI Theme Colors
COLOR_RESET = "\033[0m"
COLOR_THEME = "\033[1;96m"   # High-contrast Theme Cyan (高亮主题青色)
COLOR_NUM   = "\033[1;97m"   # High-contrast Bright White (数值常规高亮)
COLOR_YELLOW = "\033[1;93m"  # High-contrast Bright Yellow (达到20% / 剩余50% 告警)
COLOR_RED   = "\033[1;91m"   # High-contrast Bright Red (达到50% / 剩余20% 危险)

ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
EFFORT_RE = re.compile(r'\((low|medium|high|xhigh|max)\)', re.IGNORECASE)
EFFORT_CLEAN_RE = re.compile(r'\s*\((low|medium|high|xhigh|max)\)', re.IGNORECASE)

_cached_settings = None


def get_settings():
    """Retrieve and cache settings.json contents for the current invocation."""
    global _cached_settings
    if _cached_settings is not None:
        return _cached_settings
    try:
        env_dir = os.environ.get("ANTIGRAVITY_CONFIG_DIR") or os.environ.get("AGY_CONFIG_DIR")
        base = Path(env_dir) if env_dir else Path.home() / ".gemini" / "antigravity-cli"
        settings_path = base / "settings.json"
        if settings_path.exists():
            with open(settings_path, "r", encoding="utf-8") as f:
                _cached_settings = json.load(f)
                return _cached_settings
    except Exception:
        pass
    _cached_settings = {}
    return _cached_settings


def is_debug_enabled(settings=None):
    """Check if debug logging is enabled via environment variable or settings.json."""
    env_debug = os.environ.get("AGY_STATUSLINE_DEBUG", "").strip().lower()
    if env_debug in ("1", "true", "yes", "on"):
        return True
    if settings is None:
        settings = get_settings()
    if isinstance(settings, dict):
        sl_cfg = settings.get("statusLine")
        if isinstance(sl_cfg, dict) and sl_cfg.get("debug"):
            return True
        if settings.get("debug"):
            return True
    return False


if sys.platform == "win32":
    try:
        kernel32 = ctypes.windll.kernel32
        hOut = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(hOut, ctypes.byref(mode)):
            mode.value |= 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(hOut, mode)
    except Exception:
        pass

def get_terminal_width(payload=None):
    if payload and isinstance(payload, dict):
        tw = payload.get("terminal_width")
        if tw and isinstance(tw, int) and tw > 0:
            return tw

    cols = os.environ.get("COLUMNS")
    if cols and cols.isdigit():
        return int(cols)

    try:
        kernel32 = ctypes.windll.kernel32
        for handle_id in [-12, -11]:
            handle = kernel32.GetStdHandle(handle_id)
            csbi = ctypes.create_string_buffer(22)
            if kernel32.GetConsoleScreenBufferInfo(handle, csbi):
                (_, _, _, _, _, left, _, right, _, _, _) = struct.unpack("hhhhHhhhhhh", csbi.raw)
                width = right - left + 1
                if width > 0:
                    return width
    except Exception:
        pass

    try:
        with open("CONOUT$", "w") as f:
            return os.get_terminal_size(f.fileno()).columns
    except Exception:
        pass

    try:
        return os.get_terminal_size().columns
    except Exception:
        pass

    return 80

def get_display_width(text):
    clean_text = ANSI_ESCAPE_RE.sub('', text)
    if clean_text.isascii():
        return len(clean_text)
    width = 0
    for ch in clean_text:
        if ord(ch) < 128:
            width += 1
        elif unicodedata.east_asian_width(ch) in ('F', 'W'):
            width += 2
        else:
            width += 1
    return width


def format_tokens(num):
    if not num:
        return "0"
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}k"
    return str(num)

def format_context(tokens, pct):
    tok_str = format_tokens(tokens)
    if pct is not None:
        # Context 达到 20% 黄色高亮、达到 50% 红色高亮
        if pct >= 50.0:
            val_color = COLOR_RED
        elif pct >= 20.0:
            val_color = COLOR_YELLOW
        else:
            val_color = COLOR_NUM
        return f"Context: {val_color}{tok_str} ({pct:.1f}%){COLOR_RESET}"
    return f"Context: {COLOR_NUM}{tok_str}{COLOR_RESET}"


def extract_effort(payload, raw_model, settings=None):
    # 1. Direct effort field from payload or model
    model_obj = payload.get("model", {}) if isinstance(payload.get("model"), dict) else {}
    effort = (
        payload.get("effort")
        or payload.get("reasoning_effort")
        or model_obj.get("effort")
        or model_obj.get("reasoning_effort")
    )
    if effort:
        return str(effort).capitalize()

    # 2. Extract from model name string, e.g. "Gemini 3.8 Flash (High)"
    if raw_model:
        m = EFFORT_RE.search(raw_model)
        if m:
            return m.group(1).capitalize()

    # 3. Environment variable
    env_effort = os.environ.get("AGY_EFFORT") or os.environ.get("CLAUDE_CODE_EFFORT_LEVEL")
    if env_effort:
        return env_effort.capitalize()

    # 4. Fallback settings.json
    if settings is None:
        settings = get_settings()
    if settings:
        s_model = settings.get("model", "")
        m = EFFORT_RE.search(s_model)
        if m:
            return m.group(1).capitalize()
        if settings.get("effort"):
            return str(settings["effort"]).capitalize()

    return "High"

def select_quota_bucket(quota_dict, model_name):
    if not quota_dict or not isinstance(quota_dict, dict):
        return None

    model_lower = (model_name or "").lower()
    is_gemini = "gemini" in model_lower
    is_3p = any(k in model_lower for k in ["claude", "opus", "sonnet", "gpt", "openai"])

    # Match prioritized quota buckets according to model family
    if is_gemini:
        candidates = ["gemini-5h", "gemini", "gemini-weekly"]
    elif is_3p:
        candidates = ["3p-5h", "3p", "3p-weekly", "claude-5h", "claude"]
    else:
        candidates = ["gemini-5h", "3p-5h", "default"]

    for key in candidates:
        if key in quota_dict and isinstance(quota_dict[key], dict):
            return quota_dict[key]

    # Fuzzy match with "5h" prioritized for sliding window
    for k, v in quota_dict.items():
        if isinstance(v, dict) and "5h" in k:
            return v

    for v in quota_dict.values():
        if isinstance(v, dict):
            return v

    return None

def extract_quota(payload, raw_model):
    quota_data = payload.get("quota")
    if not quota_data:
        return None

    bucket = select_quota_bucket(quota_data, raw_model)
    if not bucket or not isinstance(bucket, dict):
        return None

    rem = None
    val_str = None

    if "remaining_fraction" in bucket:
        rem = float(bucket["remaining_fraction"]) * 100.0
        if rem >= 99.995:
            val_str = "100%"
        elif rem <= 0.005:
            val_str = "0%"
        else:
            val_str = f"{rem:.2f}%"
    elif "remaining_percentage" in bucket:
        rem = float(bucket["remaining_percentage"])
        val_str = f"{rem:.2f}%" if rem < 100 else "100%"
    elif "used_percentage" in bucket:
        rem = 100.0 - float(bucket["used_percentage"])
        val_str = f"{rem:.2f}%" if rem < 100 else "100%"
    elif "credits_remaining" in bucket and "credits_total" in bucket:
        c_rem = bucket["credits_remaining"]
        c_tot = bucket["credits_total"]
        if c_tot > 0:
            rem = (float(c_rem) / float(c_tot)) * 100.0
        val_str = f"{c_rem}/{c_tot}"

    if not val_str:
        return None

    # Quota 剩余 50% 黄色，剩余 20% 红色
    if rem is not None:
        if rem <= 20.0:
            color = COLOR_RED
        elif rem <= 50.0:
            color = COLOR_YELLOW
        else:
            color = COLOR_NUM
    else:
        color = COLOR_NUM

    return f"Quota: {color}{val_str}{COLOR_RESET}"


def extract_execution_mode(payload, settings=None):
    mode = (
        payload.get("execution_mode")
        or payload.get("cycle_mode")
        or payload.get("agent_mode")
    )
    if not mode:
        if settings is None:
            settings = get_settings()
        if settings:
            mode = settings.get("execution_mode") or settings.get("agentMode")

    if not mode:
        return None

    mode_str = str(mode).strip()
    if not mode_str or mode_str.lower() in ("default", "none"):
        return None

    return "-".join(part.capitalize() for part in mode_str.replace("_", "-").split("-"))

def main():
    try:
        raw_input = sys.stdin.read().strip()
        settings = get_settings()

        # Debug record: only write when debug is explicitly enabled
        if is_debug_enabled(settings):
            try:
                env_dir = os.environ.get("ANTIGRAVITY_CONFIG_DIR") or os.environ.get("AGY_CONFIG_DIR")
                base = Path(env_dir) if env_dir else Path.home() / ".gemini" / "antigravity-cli"
                dbg_file = base / "last_statusline_payload.json"
                with open(dbg_file, "w", encoding="utf-8") as f:
                    f.write(raw_input)
            except Exception:
                pass

        payload = {}
        if raw_input:
            payload = json.loads(raw_input)

        ctx = payload.get("context_window", {})
        tokens = ctx.get("total_input_tokens") or ctx.get("input_tokens") or 0
        pct = ctx.get("used_percentage")
        if pct is None and ctx.get("remaining_percentage") is not None:
            pct = 100.0 - float(ctx["remaining_percentage"])

        model_obj = payload.get("model", {})
        raw_model = ""
        if isinstance(model_obj, dict):
            raw_model = model_obj.get("display_name") or model_obj.get("name") or model_obj.get("id") or ""
        elif model_obj:
            raw_model = str(model_obj)

        if not raw_model and settings:
            raw_model = settings.get("model", "")

        effort = extract_effort(payload, raw_model, settings)

        cleaned_model = EFFORT_CLEAN_RE.sub('', raw_model).strip()
        if not cleaned_model:
            cleaned_model = "Gemini 3.8 Flash"

        parts = []
        if effort:
            parts.append(f"[{cleaned_model} · {effort}]")
        else:
            parts.append(f"[{cleaned_model}]")

        token_str = format_context(tokens, pct)
        parts.append(token_str)

        quota_str = extract_quota(payload, raw_model)
        if quota_str:
            parts.append(quota_str)

        right_text = " | ".join(parts)
        mode = extract_execution_mode(payload, settings)
        left_text = f"{COLOR_THEME}[{mode}]{COLOR_RESET}" if mode else ""

        term_width = get_terminal_width(payload)
        right_width = get_display_width(right_text)

        if left_text:
            left_width = get_display_width(left_text)
            gap = term_width - left_width - right_width - 1
            if gap >= 1:
                print(f"{left_text}{' ' * gap}{right_text}")
            else:
                combined = f"{left_text} | {right_text}"
                combined_width = get_display_width(combined)
                padding = max(0, term_width - combined_width - 1)
                print(" " * padding + combined)
        else:
            padding = max(0, term_width - right_width - 1)
            print(" " * padding + right_text)

    except Exception:
        pass


if __name__ == "__main__":
    main()
