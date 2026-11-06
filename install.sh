#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v docker >/dev/null; then
  echo "Docker Engine and Docker Compose v2 are required." >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required." >&2
  exit 1
fi
random_hex() {
  if command -v openssl >/dev/null; then openssl rand -hex "$1"
  else python3 -c "import secrets,sys;print(secrets.token_hex(int(sys.argv[1])))" "$1"; fi
}
if [[ ! -e .env ]]; then
  PASS="$(random_hex 20)"
  VERIFY="$(random_hex 24)"
  umask 077
  cat > .env <<EOF
APP_ENV=development
COOKIE_SECURE=false
DB_PATH=/srv/data/mehrad.sqlite3
BOOTSTRAP_ADMIN_EMAIL=admin@localhost
BOOTSTRAP_ADMIN_PASSWORD=$PASS
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-mini
META_APP_SECRET=
META_VERIFY_TOKEN=$VERIFY
META_ACCESS_TOKEN=
META_IG_USER_ID=
META_GRAPH_VERSION=v25.0
EOF
  printf "URL: http://127.0.0.1:8787\nEmail: admin@localhost\nPassword: %s\n" "$PASS" > .local-credentials.txt
  chmod 600 .env .local-credentials.txt
  echo "Credentials created in .local-credentials.txt"
else
  echo "Existing .env preserved."
fi
docker compose up --build -d
echo "Dashboard: http://127.0.0.1:8787"
echo "Set OPENAI_API_KEY in .env then restart to enable actual AI generation."
