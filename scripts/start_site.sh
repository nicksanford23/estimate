#!/bin/bash
# start_site.sh — bring the demo + ops dashboard up with a public URL.
# NO Claude needed. Run from a Codespace terminal:
#   bash scripts/start_site.sh
# Wait ~60s; it prints the public URL at the end (also saved to SITE_URL.txt).
# Safe to re-run anytime (kills old instances first).

set -u
cd "$(dirname "$0")/.."

echo "[1/4] stopping old instances..."
# NOTE: patterns use the [x]bracket trick so this pkill never matches the
# shell running start_site.sh itself (pkill -f matches full command lines).
pkill -f "[w]ebserver_supervisor" 2>/dev/null
pkill -f "[p]rodserver_supervisor" 2>/dev/null
pkill -f "[n]ext start -p 3311" 2>/dev/null
pkill -f "[n]ext dev -p 3311" 2>/dev/null
# Next 16 replaces the npm/CLI command with a `next-server` child whose
# process title no longer contains `next start`; without this, an orphan can
# keep serving a stale build while the new supervisor loops on EADDRINUSE.
pkill -f "[n]ext-server" 2>/dev/null
pkill -f "[c]loudflared tunnel" 2>/dev/null
sleep 2

# PRODUCTION mode, not dev. Cloudflare quick tunnels do NOT proxy the Next
# dev HMR WebSocket (/_next/webpack-hmr → 502); without it the dev client
# never finishes hydrating and EVERY button is dead over the tunnel. A
# production build has no HMR socket, so it hydrates and works remotely.
echo "[2/4] building production bundle (next build)..."
( cd /workspaces/estimate/web && npx next build ) >> /tmp/nextprod.log 2>&1 || {
  echo "  BUILD FAILED — see /tmp/nextprod.log"; tail -20 /tmp/nextprod.log; exit 1;
}

echo "      starting web server (supervised, auto-restarts if it dies)..."
cat > /tmp/prodserver_supervisor.sh <<'EOF'
#!/bin/bash
cd /workspaces/estimate/web
while true; do
  npx next start -p 3311 -H 0.0.0.0 >> /tmp/nextprod.log 2>&1
  echo "[supervisor] next start died, restarting in 3s" >> /tmp/nextprod.log
  sleep 3
done
EOF
chmod +x /tmp/prodserver_supervisor.sh
setsid nohup /tmp/prodserver_supervisor.sh >/dev/null 2>&1 < /dev/null &

echo -n "      waiting for server"
for i in $(seq 1 60); do
  if curl -s -o /dev/null --max-time 3 http://localhost:3311/ops; then break; fi
  echo -n "."; sleep 3
done
echo " up."

echo "[3/4] starting public tunnel..."
if [ ! -x /tmp/cloudflared ]; then
  curl -sL -o /tmp/cloudflared \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
  chmod +x /tmp/cloudflared
fi
rm -f /tmp/cf.log
setsid nohup /tmp/cloudflared tunnel --url http://localhost:3311 > /tmp/cf.log 2>&1 < /dev/null &

echo -n "      waiting for tunnel"
URL=""
for i in $(seq 1 40); do
  URL=$(grep -o "https://[a-z-]*\.trycloudflare\.com" /tmp/cf.log 2>/dev/null | head -1)
  [ -n "$URL" ] && break
  echo -n "."; sleep 3
done
echo ""

echo "[4/4] done."
echo ""
if [ -n "$URL" ]; then
  echo "$URL" > SITE_URL.txt
  echo "=============================================="
  echo "  YOUR SITE (new URL each restart):"
  echo "  $URL/ops     <- mission control"
  echo "  $URL/demo    <- product prototype"
  echo "=============================================="
  echo "  (also saved to SITE_URL.txt)"
else
  echo "Tunnel failed to start — check /tmp/cf.log. The site still works"
  echo "inside the Codespace at http://localhost:3311 via the Ports tab."
fi
