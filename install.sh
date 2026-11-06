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
# Initialize encryption key without changing any existing credentials.
if ! grep -Eq '^VAULT_ENCRYPTION_KEY=[A-Za-z0-9_=-]{40,}
echo "Dashboard: http://127.0.0.1:8787"
echo "Open the dashboard Security & Connections page to add keys and test services."
 .env; then
  if grep -q '^VAULT_ENCRYPTION_KEY=' .env; then
    echo "Invalid vault encryption key: restore the original .env." >&2
    exit 1
  fi
  if command -v python3 >/dev/null; then
    VAULT_KEY="$(python3 -c 'import base64,secrets;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())')"
  else
    VAULT_KEY="$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')"
  fi
  printf '\nVAULT_ENCRYPTION_KEY=%s\n' "$VAULT_KEY" >> .env
  echo "Encrypted integration vault initialized."
fi
if ! grep -q '^AUTO_REPLY_ENABLED=' .env; then
  printf 'AUTO_REPLY_ENABLED=false\n' >> .env
fi
REV="$(git rev-parse HEAD 2>/dev/null || printf unknown)"
if grep -q '^APP_REVISION=' .env; then
  sed -i.bak "s/^APP_REVISION=.*/APP_REVISION=$REV/" .env
  rm -f .env.bak
else
  printf 'APP_REVISION=%s\n' "$REV" >> .env
fi
chmod 600 .env
docker compose up --build -d
echo "Dashboard: http://127.0.0.1:8787"
echo "Set OPENAI_API_KEY in .env then restart to enable actual AI generation."
