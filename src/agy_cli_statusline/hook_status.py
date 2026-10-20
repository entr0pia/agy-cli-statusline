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

def parse_varint(data: bytes, offset: int):
    res = 0
    shift = 0
    while offset < len(data):
        b = data[offset]
        offset += 1
        res |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return res, offset

def extract_actual_model_from_blob(data: bytes) -> str | None:
    if not data:
        return None
    # Parse top-level message to find field 1 (tag = 0x0a)
    offset = 0
    field1_bytes = None
    while offset < len(data):
        tag, offset = parse_varint(data, offset)
        wire_type = tag & 7
        field_num = tag >> 3
        if wire_type == 0:
            while offset < len(data) and (data[offset] & 0x80):
                offset += 1
            offset = min(offset + 1, len(data))
        elif wire_type == 2:
            length, offset = parse_varint(data, offset)
            if field_num == 1:
                field1_bytes = data[offset : offset + length]
                break
            offset += length
        elif wire_type == 1:
            offset += 8
        elif wire_type == 5:
            offset += 4
        else:
            break

    if not field1_bytes:
        return None

    # Inside field 1, find field 19 (actual model ID)
    offset = 0
    while offset < len(field1_bytes):
        tag, offset = parse_varint(field1_bytes, offset)
        wire_type = tag & 7
        field_num = tag >> 3
        if wire_type == 0:
            while offset < len(field1_bytes) and (field1_bytes[offset] & 0x80):
                offset += 1
            offset = min(offset + 1, len(field1_bytes))
        elif wire_type == 2:
            length, offset = parse_varint(field1_bytes, offset)
            if field_num == 19:
                try:
                    return field1_bytes[offset : offset + length].decode("utf-8")
                except Exception:
                    return None
            offset += length
        elif wire_type == 1:
            offset += 8
        elif wire_type == 5:
            offset += 4
        else:
            break
    return None

def get_actual_model_for_session(conversation_id: str | None) -> str | None:
    if not conversation_id:
        return None
    import sqlite3
    roots = [
        Path.home() / ".gemini" / "antigravity" / "conversations",
        Path.home() / ".gemini" / "antigravity-cli" / "conversations",
    ]
    for r in roots:
        db_path = r / f"{conversation_id}.db"
        if db_path.exists():
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                cur = conn.cursor()
                cur.execute("SELECT data FROM gen_metadata ORDER BY idx DESC LIMIT 1;")
                row = cur.fetchone()
                conn.close()
                if row and row[0]:
                    model = extract_actual_model_from_blob(row[0])
                    if model:
                        return model
            except Exception:
                pass
    return None

def extract_step_tps(conversation_id: str | None, step_idx: int | None = None) -> float | None:
    if not conversation_id:
        return None
    import sqlite3
    roots = [
        Path.home() / ".gemini" / "antigravity" / "conversations",
        Path.home() / ".gemini" / "antigravity-cli" / "conversations",
    ]
    for r in roots:
        db_path = r / f"{conversation_id}.db"
        if db_path.exists():
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                cur = conn.cursor()
                row = None
                if step_idx is not None:
                    cur.execute("SELECT metadata FROM steps WHERE idx = ? AND step_type = 15 LIMIT 1;", (step_idx,))
                    row = cur.fetchone()
                if not row:
                    cur.execute("SELECT metadata FROM steps WHERE step_type = 15 ORDER BY idx DESC LIMIT 1;")
                    row = cur.fetchone()
                conn.close()
                if row and row[0]:
                    data = row[0]
                    # Simple protobuf parse to get field 6 (start time), field 7 (end time), field 9.field 3 (tokens)
                    offset = 0
                    f6_start = None
                    f7_end = None
                    out_tokens = None
                    while offset < len(data):
                        tag, offset = parse_varint(data, offset)
                        wire_type = tag & 7
                        field_num = tag >> 3
                        if wire_type == 0:
                            _, offset = parse_varint(data, offset)
                        elif wire_type == 2:
                            length, offset = parse_varint(data, offset)
                            sub = data[offset : offset + length]
                            offset += length
                            if field_num in (6, 7):
                                # Timestamp message: field 1 = sec, field 2 = nsec
                                s_off = 0
                                sec = 0
                                nsec = 0
                                while s_off < len(sub):
                                    s_tag, s_off = parse_varint(sub, s_off)
                                    s_wire = s_tag & 7
                                    s_num = s_tag >> 3
                                    if s_wire == 0:
                                        s_val, s_off = parse_varint(sub, s_off)
                                        if s_num == 1:
                                            sec = s_val
                                        elif s_num == 2:
                                            nsec = s_val
                                    else:
                                        break
                                if field_num == 6:
                                    f6_start = sec + nsec / 1e9
                                elif field_num == 7:
                                    f7_end = sec + nsec / 1e9
                            elif field_num == 9:
                                # Usage message: field 3 = output_tokens
                                u_off = 0
                                while u_off < len(sub):
                                    u_tag, u_off = parse_varint(sub, u_off)
                                    u_wire = u_tag & 7
                                    u_num = u_tag >> 3
                                    if u_wire == 0:
                                        u_val, u_off = parse_varint(sub, u_off)
                                        if u_num == 3:
                                            out_tokens = u_val
                                    else:
                                        break
                        elif wire_type == 1:
                            offset += 8
                        elif wire_type == 5:
                            offset += 4
                        else:
                            break

                    if f6_start and f7_end and out_tokens:
                        dur = f7_end - f6_start
                        if dur > 0.05 and out_tokens > 0:
                            return out_tokens / dur
            except Exception:
                pass
    return None

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
        conversation_id = payload.get("conversationId")
        if not conversation_id and transcript_path:
            try:
                conversation_id = Path(transcript_path).parent.parent.parent.name
            except Exception:
                pass

        actual_model = get_actual_model_for_session(conversation_id) or model_name

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
        max_context = get_context_limit(actual_model)
        pct = (total_prompt / max_context) * 100 if max_context > 0 else 0.0

        # Status icon based on percentage
        if pct >= 50.0:
            badge = "🔴"
        elif pct >= 20.0:
            badge = "🟡"
        else:
            badge = "🟢"

        cache_pct = (cache_read / total_prompt * 100) if total_prompt > 0 else 0.0

        tps = extract_step_tps(conversation_id, last.get("step_index"))
        speed_str = f" | 🚀 **Speed**: {tps:.1f} TPS" if tps else ""

        line1 = (
            f"🤖 **Model**: `{actual_model}`{speed_str} | "
            f"{badge} **Context**: {format_tokens(total_prompt)} / {format_tokens(max_context)} ({pct:.1f}%)"
        )
        line2 = (
            f"⚡ **Cache**: {format_tokens(cache_read)} ({cache_pct:.0f}%) | "
            f"📥 **Input**: {format_tokens(input_tokens)} | "
            f"📤 **Output**: {format_tokens(output_tokens)} | "
            f"🛠️ **Tools**: {tool_call_count}"
        )

        msg = f"\n{line1}  \n{line2}"

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
