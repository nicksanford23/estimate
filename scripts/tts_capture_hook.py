#!/usr/bin/env python3
"""Stop hook: capture the assistant's last message into data/tts_messages/.

Reads the hook input JSON on stdin (contains transcript_path), pulls the final
assistant message's text, and writes it as a timestamped .md the TTS page
(scripts/tts_server.mjs) lists for click-to-listen. Keeps the newest 40 files.
Never blocks the session: any failure exits 0 silently.
"""
import json
import os
import sys
import time


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    tp = payload.get("transcript_path")
    if not tp or not os.path.exists(tp):
        return
    last_text = None
    try:
        with open(tp) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                msg = rec.get("message") if isinstance(rec, dict) else None
                if not isinstance(msg, dict) or msg.get("role") != "assistant":
                    continue
                content = msg.get("content")
                parts = []
                if isinstance(content, str):
                    parts = [content]
                elif isinstance(content, list):
                    parts = [b.get("text", "") for b in content
                             if isinstance(b, dict) and b.get("type") == "text"]
                text = "\n\n".join(p for p in parts if p).strip()
                if text:
                    last_text = text
    except Exception:
        return
    if not last_text or len(last_text) < 120:
        return
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data", "tts_messages")
    try:
        os.makedirs(out_dir, exist_ok=True)
        # First non-empty line (sans markdown furniture) becomes the button label.
        first = next((l.strip().lstrip("#*-• ") for l in last_text.splitlines() if l.strip()), "reply")
        slug = "".join(c if c.isalnum() or c in " -" else "" for c in first)[:40].strip().replace(" ", "-").lower() or "reply"
        name = time.strftime("%Y%m%d-%H%M%S") + "-" + slug + ".md"
        with open(os.path.join(out_dir, name), "w") as f:
            f.write(last_text)
        files = sorted(f for f in os.listdir(out_dir) if f.endswith(".md"))
        for old in files[:-40]:
            os.remove(os.path.join(out_dir, old))
    except Exception:
        return


if __name__ == "__main__":
    main()
