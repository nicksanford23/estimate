#!/bin/bash
# Run SQL against our Neon schema (estimate.*). Usage:
#   scripts/db.sh "SELECT ..."         one statement, rows printed a|b|c
#   echo "SQL; SQL;" | scripts/db.sh   multiple statements from stdin
# search_path is set to estimate, so unqualified table names hit our schema.
SQL="${1:-$(cat)}" python3 - <<'EOF'
import os, sys
import psycopg2
env = {}
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__ if '__file__' in dir() else 'scripts/x')))
for line in open(os.path.join("/workspaces/estimate", ".env")):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k] = v
conn = psycopg2.connect(env["NEON_DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()
cur.execute("SET search_path TO estimate, public")
cur.execute(os.environ["SQL"])
if cur.description:
    for row in cur.fetchall():
        print("|".join("" if c is None else str(c) for c in row))
conn.close()
EOF
