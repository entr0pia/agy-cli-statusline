# -*- coding: utf-8 -*-
import sys
import os
import json
import re
import ctypes
import struct
import unicodedata
from pathlib import Path

# Ensure UTF-8 I/O on Windows without CRLF translation
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

# ANSI Theme Colors (Standard ECMA-48 Compliant Bold Sequences)
COLOR_RESET = "\033[0m"
COLOR_THEME_DEFAULT = "\033[1;36m"  # High-contrast Bright Cyan default (ECMA-48 Bold Cyan)
COLOR_NUM   = "\033[1;37m"          # High-contrast Bright White (ECMA-48 Bold White)
COLOR_YELLOW = "\033[1;33m"         # High-contrast Bright Yellow (ECMA-48 Bold Yellow)
COLOR_RED   = "\033[1;31m"          # High-contrast Bright Red (ECMA-48 Bold Red)

# Standard Named ANSI Colors (Bold)
NAMED_ANSI_COLORS = {
    "cyan": "\033[1;36m",
    "blue": "\033[1;34m",
    "purple": "\033[1;35m",
    "magenta": "\033[1;35m",
    "green": "\033[1;32m",
    "yellow": "\033[1;33m",
    "red": "\033[1;31m",
    "white": "\033[1;37m",
    "gray": "\033[1;30m",
    "grey": "\033[1;30m",
}

# agy Official Theme Accent Palettes
THEME_PALETTES = {
    "tokyo night": "\033[1;38;2;122;162;247m",          # #7aa2f7 Tokyo Blue
    "tokyonight": "\033[1;38;2;122;162;247m",
    "solarized dark": "\033[1;38;2;42;161;152m",        # #2aa198 Solarized Cyan
    "solarized-dark": "\033[1;38;2;42;161;152m",
    "solarized light": "\033[1;38;2;38;139;210m",       # #268bd2 Solarized Blue
    "solarized-light": "\033[1;38;2;38;139;210m",
    "light": "\033[1;38;2;9;105;218m",                 # #0969da High-contrast Dark Blue
    "dark": "\033[1;96m",                               # Bright Cyan
    "terminal": "\033[1;36m",                           # Terminal Cyan
    "colorblind-friendly dark": "\033[1;38;2;51;177;255m",   # #33b1ff Sky Blue
    "colorblind-friendly light": "\033[1;38;2;51;177;255m",  # #33b1ff Sky Blue
    "colorblind-friendly": "\033[1;38;2;51;177;255m",
}


def hex_to_ansi(hex_str):
    """Convert hex string (e.g. #7aa2f7 or 7aa2f7) to 24-bit TrueColor ANSI escape."""
    if not hex_str or not isinstance(hex_str, str):
        return None
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return None
    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return f"\033[1;38;2;{r};{g};{b}m"
    except ValueError:
        return None


def parse_color_code(val):
    """Parse color from user input (hex, named color, or raw ANSI)."""
    if not val or not isinstance(val, str):
        return None
    cleaned = val.strip()
    if not cleaned:
        return None
    # 1. Raw ANSI code
    if "\033" in cleaned or "\x1b" in cleaned:
        return cleaned
    # 2. Named color
    lower = cleaned.lower()
    if lower in NAMED_ANSI_COLORS:
        return NAMED_ANSI_COLORS[lower]
    # 3. Hex code
    hex_ansi = hex_to_ansi(cleaned)
    if hex_ansi:
        return hex_ansi
    return None


def resolve_theme_color(payload=None, settings=None):
    """Resolve the statusline theme color dynamically according to custom config, colorScheme, or default."""
    if settings is None:
        settings = get_settings()

    # 1. Check settings.json statusLine override
    if isinstance(settings, dict):
        sl = settings.get("statusLine")
        if isinstance(sl, dict):
            custom_color = sl.get("themeColor") or sl.get("color")
            parsed = parse_color_code(custom_color)
            if parsed:
                return parsed

    # 2. Check environment variables
    env_color = os.environ.get("AGY_THEME_COLOR") or os.environ.get("AGY_STATUSLINE_COLOR")
    parsed_env = parse_color_code(env_color)
    if parsed_env:
        return parsed_env

    # 3. Check payload for theme/colorScheme (forward compatibility)
    if isinstance(payload, dict):
        p_scheme = payload.get("colorScheme") or payload.get("theme") or payload.get("color_scheme")
        if p_scheme and isinstance(p_scheme, str):
            p_norm = p_scheme.strip().lower()
            if p_norm in THEME_PALETTES:
                return THEME_PALETTES[p_norm]
            p_key = p_norm.replace("-", " ")
            if p_key in THEME_PALETTES:
                return THEME_PALETTES[p_key]

    # 4. Check agy colorScheme in settings.json
    if isinstance(settings, dict):
        scheme = settings.get("colorScheme")
        if scheme and isinstance(scheme, str):
            norm_scheme = scheme.strip().lower()
            if norm_scheme in THEME_PALETTES:
                return THEME_PALETTES[norm_scheme]
            key = norm_scheme.replace("-", " ")
            if key in THEME_PALETTES:
                return THEME_PALETTES[key]

    return COLOR_THEME_DEFAULT


ANSI_ESCAPE_RE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
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
        with open("CONOUT$", "r") as f:
            return os.get_terminal_size(f.fileno()).columns
    except Exception:
        pass

    try:
        import shutil
        return shutil.get_terminal_size((80, 20)).columns
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
        elif unicodedata.east_asian_width(ch) in ('F', 'W', 'A'):
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
            clean_input = ANSI_ESCAPE_RE.sub('', raw_input).strip()
            start_idx = clean_input.find('{')
            end_idx = clean_input.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
                clean_input = clean_input[start_idx:end_idx + 1]
            try:
                payload = json.loads(clean_input)
            except Exception:
                try:
                    payload = json.loads(raw_input)
                except Exception:
                    payload = {}

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
        theme_color = resolve_theme_color(payload, settings)
        left_text = f"{theme_color}[{mode}]{COLOR_RESET}" if mode else ""
        left_width = get_display_width(left_text) if left_text else 0

        term_width = get_terminal_width(payload)
        right_width = get_display_width(right_text)

        # Reserve 1 column for terminal safety margin (VT auto-margin / line wrap protection)
        safety_margin = 1
        max_avail = max(20, term_width - safety_margin)

        # Multi-tiered layout to strictly guarantee no terminal wrapping or ANSI truncation
        def fit_right_content(avail):
            # 1. Full right text
            if right_width <= avail:
                pad = max(0, avail - right_width)
                return " " * pad + right_text
            # 2. Drop Quota
            compact_parts = [p for p in parts if not p.startswith("Quota:")]
            compact_right = " | ".join(compact_parts)
            compact_width = get_display_width(compact_right)
            if compact_width <= avail:
                pad = max(0, avail - compact_width)
                return " " * pad + compact_right
            # 3. Drop Model name, keep Context token status
            ctx_width = get_display_width(token_str)
            if ctx_width <= avail:
                pad = max(0, avail - ctx_width)
                return " " * pad + token_str
            # 4. Ultra compact (just numbers)
            tok_num_str = format_tokens(tokens)
            short_str = f"Ctx:{COLOR_NUM}{tok_num_str}{COLOR_RESET}"
            short_w = get_display_width(short_str)
            pad = max(0, avail - short_w)
            return " " * pad + short_str

        if left_text:
            gap = max_avail - left_width - right_width
            if gap >= 2:
                final_line = f"{left_text}{' ' * gap}{right_text}"
            else:
                combined = f"{left_text} | {right_text}"
                combined_width = get_display_width(combined)
                if combined_width <= max_avail:
                    padding = max(0, max_avail - combined_width)
                    final_line = " " * padding + combined
                else:
                    final_line = fit_right_content(max_avail)
        else:
            final_line = fit_right_content(max_avail)

        sys.stdout.write(final_line)
        sys.stdout.flush()

    except Exception:
        pass


if __name__ == "__main__":
    main()
