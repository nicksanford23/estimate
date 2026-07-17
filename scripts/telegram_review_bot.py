#!/usr/bin/env python3
"""Telegram review loop for room-outline proposals — stdlib only (urllib).

Sends per-room proposal cards (overlay image + caption) to Nick's chat and
records his replies as APPEND-ONLY human decision events. This is the
"tap = truth" transport: nothing here mutates proposals; a LOCK reply
appends a human outcome row in the same JSONL contract the editor uses
(data/geometry_annotations/human/<permit>.outcomes.jsonl), with
reviewer="nick:telegram" and the proposal polygon it locked.

Setup (one-time, by Nick):
  1. @BotFather -> /newbot -> put token in .env: TELEGRAM_BOT_TOKEN=...
  2. Send the bot any message; then run: telegram_review_bot.py whoami
     -> prints chat id; put it in .env: TELEGRAM_CHAT_ID=...

Commands:
  whoami                      discover chat id from recent messages
  send --permit P [--codes 204,209 | --batch bet|check|all]
                              send card(s): overlay image + caption
  listen --permit P           poll replies; "LOCK 204" / "LOCK 1-24" /
                              "SKIP 204 <reason>" appended as outcomes;
                              anything else logged as a note for the driver
Replies are matched to the most recent batch sent (state in
data/telegram/state_<permit>.json). Free-text fix requests ("204 extend to
the right wall") are NOT auto-applied — they are logged to
data/telegram/fix_requests_<permit>.jsonl for the driver/agents to redraw
and re-send. Nothing is deleted, ever.
"""
import argparse
import json
import os
import time
import urllib.request
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env():
    env = {}
    with open(os.path.join(ROOT, ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env


ENV = load_env()
API = "https://api.telegram.org/bot{token}/{method}"


def tg(method, params=None, files=None, timeout=60):
    token = ENV.get("TELEGRAM_BOT_TOKEN")
    assert token, "TELEGRAM_BOT_TOKEN missing from .env (see docstring setup)"
    url = API.format(token=token, method=method)
    if files:
        # minimal multipart encoder (stdlib only)
        boundary = "----estimatebot%d" % int(time.time())
        body = b""
        for k, v in (params or {}).items():
            body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                     % (boundary, k, v)).encode()
        for k, (fname, data) in files.items():
            body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                     "Content-Type: application/octet-stream\r\n\r\n" % (boundary, k, fname)).encode()
            body += data + b"\r\n"
        body += ("--%s--\r\n" % boundary).encode()
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "multipart/form-data; boundary=%s" % boundary})
    else:
        data = urllib.parse.urlencode(params or {}).encode()
        req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def whoami():
    d = tg("getUpdates", {"timeout": 0})
    seen = {}
    for u in d.get("result", []):
        m = u.get("message") or {}
        c = m.get("chat") or {}
        if c.get("id"):
            seen[c["id"]] = c.get("first_name") or c.get("title") or "?"
    if not seen:
        print("no messages yet — send the bot a 'hi' first, then rerun")
    for cid, name in seen.items():
        print(f"chat id: {cid}  ({name})  -> add to .env: TELEGRAM_CHAT_ID={cid}")


def smoke_paths(permit):
    base = os.path.join(ROOT, "data", "sam_smoke", permit)
    props = os.path.join(base, "results", "proposals_for_editor.json")
    return base, props


def load_batchable(permit):
    base, props_path = smoke_paths(permit)
    props = json.load(open(props_path))
    cards = []
    for task_id, p in props.items():
        code = p["code"]
        overlay = os.path.join(base, "claude_vision", f"overlay_{code}.png")
        if not os.path.exists(overlay):
            continue
        conf = p.get("confidence") or 0
        bucket = "bet" if conf >= 0.5 else "check"
        cards.append(dict(task_id=task_id, code=code, overlay=overlay,
                          confidence=conf, bucket=bucket,
                          outcome=p.get("outcome_suggestion"),
                          notes=p.get("boundary_notes", []),
                          polygon_pdf=p["polygon_pdf"],
                          proposal_source=p.get("proposal_source")))
    return sorted(cards, key=lambda c: (-c["confidence"], c["code"]))


def state_path(permit):
    d = os.path.join(ROOT, "data", "telegram")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"state_{permit}.json")


def send(permit, codes=None, batch="bet"):
    chat = ENV.get("TELEGRAM_CHAT_ID")
    assert chat, "TELEGRAM_CHAT_ID missing from .env (run whoami)"
    cards = load_batchable(permit)
    if codes:
        want = set(codes.split(","))
        cards = [c for c in cards if c["code"] in want]
    elif batch != "all":
        cards = [c for c in cards if c["bucket"] == batch]
    assert cards, "no cards matched"
    sent = {}
    for c in cards:
        note = (c["notes"] or ["(no notes)"])[0][:180]
        cap = (f"Room {c['code']} — {c['outcome']} — confidence {c['confidence']:.2f}\n"
               f"{note}\n"
               f"Reply:  LOCK {c['code']}   |   SKIP {c['code']} <why>   |   describe the fix")
        with open(c["overlay"], "rb") as f:
            data = f.read()
        r = tg("sendPhoto", {"chat_id": chat, "caption": cap},
               files={"photo": (f"{c['code']}.png", data)})
        sent[c["code"]] = dict(task_id=c["task_id"], message_id=r["result"]["message_id"],
                               polygon_pdf=c["polygon_pdf"], outcome=c["outcome"],
                               proposal_source=c["proposal_source"])
        print("sent", c["code"], flush=True)
        time.sleep(1.1)  # rate-limit safety
    st = {"permit": permit, "sent_at": time.time(), "cards": sent}
    json.dump(st, open(state_path(permit), "w"), indent=1)
    print(f"batch of {len(sent)} sent; now run: telegram_review_bot.py listen --permit {permit}")


def append_outcome(permit, code, card, decision, notes):
    d = os.path.join(ROOT, "data", "geometry_annotations", "human")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{permit}.outcomes.jsonl")
    prior = 0
    if os.path.exists(path):
        prior = sum(1 for _ in open(path))
    row = dict(task_id=card["task_id"],
               saved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               reviewer="nick:telegram",
               outcome=card["outcome"] if decision == "lock" else "unresolved",
               boundary_types=[], open_zone_members=[],
               polygon_pdf=card["polygon_pdf"] if decision == "lock" else None,
               notes=notes, supersedes=None,
               proposal_source=card["proposal_source"],
               decision=decision, row_index=prior)
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")
    return path


def listen(permit, minutes=30):
    st = json.load(open(state_path(permit)))
    cards = st["cards"]
    offset = None
    done = set()
    fixlog = os.path.join(ROOT, "data", "telegram", f"fix_requests_{permit}.jsonl")
    t0 = time.time()
    print(f"listening for replies ({len(cards)} cards pending, {minutes} min max)...")
    while time.time() - t0 < minutes * 60 and len(done) < len(cards):
        d = tg("getUpdates", {"timeout": 25, "offset": offset or ""}, timeout=40)
        for u in d.get("result", []):
            offset = u["update_id"] + 1
            m = (u.get("message") or {})
            text = (m.get("text") or "").strip()
            if not text:
                continue
            up = text.upper().split()
            if up and up[0] in ("LOCK", "SKIP"):
                codes = [c for c in cards if c in text.upper().replace("-", " ").split()
                         or c.upper() in [w.strip(",") for w in up[1:]]]
                for code in codes:
                    if code in done:
                        continue
                    decision = "lock" if up[0] == "LOCK" else "skip"
                    reason = " ".join(text.split()[2:]) if decision == "skip" else None
                    p = append_outcome(permit, code, cards[code], decision, reason)
                    done.add(code)
                    tg("sendMessage", {"chat_id": m["chat"]["id"],
                                       "text": f"{'✅ locked' if decision=='lock' else '⏸ skipped'} {code} — recorded"})
                    print(f"{decision}: {code} -> {p}", flush=True)
            else:
                with open(fixlog, "a") as f:
                    f.write(json.dumps({"at": time.time(), "text": text}) + "\n")
                tg("sendMessage", {"chat_id": m["chat"]["id"],
                                   "text": "📝 noted for redraw — the driver will send an updated card"})
                print("fix request logged:", text[:80], flush=True)
    print(f"done: {len(done)}/{len(cards)} decided; fix requests (if any) in {fixlog}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["whoami", "send", "listen"])
    ap.add_argument("--permit", default="24-06748-RNVS")
    ap.add_argument("--codes")
    ap.add_argument("--batch", default="bet", choices=["bet", "check", "all"])
    ap.add_argument("--minutes", type=int, default=30)
    a = ap.parse_args()
    if a.cmd == "whoami":
        whoami()
    elif a.cmd == "send":
        send(a.permit, a.codes, a.batch)
    else:
        listen(a.permit, a.minutes)


if __name__ == "__main__":
    main()
