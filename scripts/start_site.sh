#!/bin/bash
# start_site.sh — bring the demo + ops dashboard up with a public URL.
# NO Claude needed. Run from a Codespace terminal:
#   bash scripts/start_site.sh
# Wait ~60s; it prints the public URL at the end (also saved to SITE_URL.txt).
# Safe to re-run anytime (kills old instances first).

set -u
cd "$(dirname "$0")/.."

echo "[1/4] stopping old instances..."
pkill -f "webserver_supervisor" 2>/dev/null
pkill -f "next dev -p 3311" 2>/dev/null
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 2

echo "[2/4] starting web server (supervised, auto-restarts if it dies)..."
cat > /tmp/webserver_supervisor.sh <<'EOF'
#!/bin/bash
cd /workspaces/estimate/web
while true; do
  npx next dev -p 3311 -H 0.0.0.0 >> /tmp/nextdev.log 2>&1
  echo "[supervisor] restarting in 3s" >> /tmp/nextdev.log
  sleep 3
done
EOF
chmod +x /tmp/webserver_supervisor.sh
setsid nohup /tmp/webserver_supervisor.sh >/dev/null 2>&1 < /dev/null &

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
