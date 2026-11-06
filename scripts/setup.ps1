$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
function New-HexSecret($length) {
  $b = New-Object byte[] $length
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($b) } finally { $rng.Dispose() }
  return [BitConverter]::ToString($b).Replace("-","").ToLowerInvariant()
}
if (!(Test-Path ".env")) {
  $password = New-HexSecret 20
  $verify = New-HexSecret 24
  $envText = @"
APP_ENV=development
COOKIE_SECURE=false
DB_PATH=/srv/data/mehrad.sqlite3
BOOTSTRAP_ADMIN_EMAIL=admin@localhost
BOOTSTRAP_ADMIN_PASSWORD=$password
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-mini
META_APP_SECRET=
META_VERIFY_TOKEN=$verify
META_ACCESS_TOKEN=
META_IG_USER_ID=
META_GRAPH_VERSION=v25.0
"@
  [System.IO.File]::WriteAllText((Join-Path (Get-Location).Path ".env"),$envText,[System.Text.Encoding]::ASCII)
  $credential = "URL: http://127.0.0.1:8787" + [Environment]::NewLine + "Email: admin@localhost" + [Environment]::NewLine + "Password: $password" + [Environment]::NewLine
  [System.IO.File]::WriteAllText((Join-Path (Get-Location).Path ".local-credentials.txt"),$credential,[System.Text.Encoding]::ASCII)
  Write-Host "Created credentials in .local-credentials.txt" -ForegroundColor Green
} else {
  Write-Host "Found existing .env - preserving all credentials." -ForegroundColor Yellow
}
docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Docker Compose v2 is required" }
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw "Docker build/start failed" }
Write-Host "Local dashboard: http://127.0.0.1:8787" -ForegroundColor Cyan
Write-Host "Edit .env to connect OpenAI and Meta, then run this script again." -ForegroundColor Yellow
