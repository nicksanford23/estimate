# Migrating to the new GitHub account (written 2026-07-22)

Everything needed to continue this project in a fresh Codespace on a new
GitHub account. All code/docs are in git; all pipeline data is backed up to
R2; only `.env` moves by hand (it holds every secret and is never in git).

## Step 1 — Move the repo (Nick, in the browser, ~2 min)

RECOMMENDED: transfer ownership (keeps history, one repo, zero commands):
Old account -> repo Settings -> Danger Zone -> "Transfer ownership" ->
type the new account's username. Accept from the new account's email.

(Alternative if transfer is undesirable: new account -> github.com/new/import
-> import from the old repo URL with a token from the old account.)

## Step 2 — Copy .env (Nick, by hand — the only manual secret step)

In THIS old Codespace terminal: `cat .env`, copy the whole output into a
password manager / private note. It contains: NEON_DATABASE_URL, R2 creds,
RUNPOD_API_KEY, TELEGRAM_BOT_TOKEN + CHAT_ID, DEEPGRAM_API_KEY.
NEVER paste it into chat or commit it.

## Step 3 — New Codespace (new account)

1. Open a Codespace on the transferred repo, branch `web`.
2. Create `.env` at the repo root, paste the saved contents.
3. Restore the pipeline data (measurements, proofs, truth file, crops):
   `pip install boto3 pymupdf pillow psycopg2-binary scipy` (if missing)
   `python3 scripts/backup_data_r2.py restore`
4. Web app: `cd web && npm install && npx next build && npx next start -p 3311 -H 0.0.0.0`
5. Listen page: `node scripts/tts_server.mjs` (port 8899).
6. Original plan PDFs are NOT in the backup (big, re-pullable): any doc
   fetches from R2 `docs/<doc_id>.pdf` on demand; scripts already do this.

## Step 4 — First Claude session on the new box

Tell it: "Read STATE.md and MIGRATION_NEW_ACCOUNT.md, verify the restore
(data/sam_smoke exists, /lab renders, outcomes JSONL present), then continue
from STATE.md's NEXT items." Claude auto-memory lives per-machine — the new
session rebuilds context from STATE.md + docs, which are current.

## What is where (so nothing is feared lost)

- Code, docs, constitution, session logs: git (branch `web`).
- Human decisions (TRUTH): data/geometry_annotations/human/*.jsonl —
  in the R2 backup AND mirrored in Neon table estimate.geometry_outcome_backup.
- Measurements/proofs/crops/floor maps: R2 backup tar
  (claude-repo/backups/data_backup_latest.tar.gz, ~187 MB).
- Plan PDFs: R2 `docs/` bucket (shared corpus, unaffected by the account move).
- Neon Postgres + R2 + RunPod + Telegram + Deepgram: all keyed via .env,
  none tied to the GitHub account — they keep working unchanged.

## Gotchas

- Codespace URLs (opulent-halibut-...) die with the old box; tunnels are
  transient anyway. New box = new URLs; scripts derive them, nothing breaks.
- The Stop-hook TTS capture + project settings travel in git (.claude/).
- Rerun `python3 scripts/backup_data_r2.py backup` before abandoning the old
  Codespace if any new work happened after this file's date.
