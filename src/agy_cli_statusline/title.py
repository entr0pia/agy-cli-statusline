# -*- coding: utf-8 -*-
import sys
import json

# 1. 顶层 I/O 优化：使用 utf-8-sig 原生自动剥离 BOM 头，避免每次循环尝试 decode
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8-sig")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STATE_EMOJIS = {
    "initializing": "🚀",
    "idle": "🤖",
    "thinking": "🤔",
    "working": "🏃",
    "tool_use": "🛠️",
}
DEFAULT_EMOJI = "🤖"

def main() -> None:
    try:
        raw_text = sys.stdin.read()
        if not raw_text:
            sys.stdout.write("unknown: 😴 idle\n")
            return

        # 2. 解析 JSON 数据
        data = json.loads(raw_text)
        agent_state = data.get("agent_state") or "idle"

        # 3. 极速路径名提取：纯切片操作替代 os.path.normpath，避免重度正则与系统调用
        workspace_obj = data.get("workspace")
        dir_path = ""
        if isinstance(workspace_obj, dict):
            dir_path = workspace_obj.get("project_dir") or workspace_obj.get("current_dir") or ""
        if not dir_path:
            dir_path = data.get("cwd") or ""

        clean_path = dir_path.rstrip("/\\")
        idx = max(clean_path.rfind("/"), clean_path.rfind("\\"))
        workspace_name = clean_path[idx + 1:] if idx != -1 else (clean_path or "unknown")

        # 4. 获取对应 Emoji
        emoji = STATE_EMOJIS.get(agent_state, DEFAULT_EMOJI)

        # 5. 快速类型判断与输出（直接用 sys.stdout.write 避免 print 额外开销）
        tc = data.get("task_count")
        if tc and isinstance(tc, int) and tc > 0:
            sys.stdout.write(f"{workspace_name}: {emoji} {agent_state} [{tc}]\n")
        else:
            sys.stdout.write(f"{workspace_name}: {emoji} {agent_state}\n")

    except Exception:
        sys.stdout.write("antigravity: 🤖 idle\n")

if __name__ == "__main__":
    main()
