import sys
import json
import os
from pathlib import Path

# Enable UTF-8 for Windows console
if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8-sig")
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)

def get_context_limit(model_name: str) -> int:
    name = (model_name or "").lower()
    if "flash" in name:
        return 1_048_576
    if "pro" in name:
        return 2_097_152
    if "claude" in name:
        return 200_000
    if "gpt" in name or "o1" in name or "o3" in name:
        return 128_000
    return 1_048_576

def main():
    try:
        # Read payload from stdin
        stdin_content = sys.stdin.read().lstrip("\ufeff")
        if not stdin_content.strip():
            sys.stdout.write(json.dumps({}))
            return

        payload = json.loads(stdin_content)
        transcript_path = payload.get("transcriptPath")
        model_name = payload.get("modelName") or "Gemini"

        if not transcript_path or not os.path.exists(transcript_path):
            sys.stdout.write(json.dumps({}))
            return

        # Parse transcript.jsonl
        lines = []
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except Exception:
                        pass

        planner_steps = [s for s in lines if s.get("type") == "PLANNER_RESPONSE"]
        if not planner_steps:
            sys.stdout.write(json.dumps({}))
            return

        last = planner_steps[-1]

        # If the last response was issuing tool calls, the turn has not finished yet.
        # Only display the statusline when the model finishes its final textual response.
        if last.get("tool_calls"):
            sys.stdout.write(json.dumps({}))
            return

        # Find the start index of the current turn (last USER_INPUT)
        last_user_idx = -1
        for i, s in enumerate(lines):
            if s.get("type") == "USER_INPUT" and s.get("source") == "USER_EXPLICIT":
                last_user_idx = i

        # Count tool calls executed during this turn
        turn_steps = lines[last_user_idx:] if last_user_idx != -1 else lines
        tool_call_count = sum(
            len(s.get("tool_calls", []))
            for s in turn_steps
            if s.get("type") == "PLANNER_RESPONSE"
        )

        input_tokens = last.get("input_tokens") or 0
        cache_read = last.get("cache_read_tokens") or 0
        output_tokens = last.get("output_tokens") or 0
        total_prompt = input_tokens + cache_read

        # Window capacity
        max_context = get_context_limit(model_name)
        pct = (total_prompt / max_context) * 100 if max_context > 0 else 0.0

        # Status icon based on percentage
        if pct >= 50.0:
            badge = "🔴"
        elif pct >= 20.0:
            badge = "🟡"
        else:
            badge = "🟢"

        cache_pct = (cache_read / total_prompt * 100) if total_prompt > 0 else 0.0

        msg = (
            f"{badge} **Context**: {format_tokens(total_prompt)} / {format_tokens(max_context)} "
            f"({pct:.1f}%) | "
            f"⚡ Cache: {format_tokens(cache_read)} ({cache_pct:.0f}%) | "
            f"📥 Input: {format_tokens(input_tokens)} | "
            f"📤 Output: {format_tokens(output_tokens)} | "
            f"🛠️ Tools: {tool_call_count}"
        )

        result = {
            "injectSteps": [
                {
                    "systemMessage": {
                        "systemMessage": msg
                    }
                }
            ]
        }
        sys.stdout.write(json.dumps(result))
    except Exception as e:
        import traceback
        sys.stderr.write(f"Error in hook_status: {e}\n{traceback.format_exc()}\n")
        sys.stdout.write(json.dumps({}))

if __name__ == "__main__":
    main()
