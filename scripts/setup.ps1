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
# Secure vault provisioning for both NEW and EXISTING installs.
$envPath=Join-Path (Get-Location).Path ".env"
$existing=[System.IO.File]::ReadAllText($envPath)
if ($existing -notmatch '(?m)^VAULT_ENCRYPTION_KEY=[A-Za-z0-9_\-=]{40,}
if ($LASTEXITCODE -ne 0) { throw "Docker Compose v2 is required" }
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw "Docker build/start failed" }
Write-Host "Local dashboard: http://127.0.0.1:8787" -ForegroundColor Cyan
Write-Host "Open Security & Connections in the dashboard to add API credentials securely." -ForegroundColor Cyan
# Start restricted host update agent: NO Docker socket is exposed to the web container.
$agent=Join-Path $PSScriptRoot "host-update-agent.ps1"
if (Test-Path $agent) {
  Start-Process -FilePath "powershell.exe" -ArgumentList @(
      "-NoProfile","-ExecutionPolicy","Bypass","-File",('"' + $agent + '"')
  ) -WindowStyle Hidden | Out-Null
  Write-Host "Host update agent initialized (polls owner-approved update tickets)." -ForegroundColor Green
}
) {
  if ($existing -match '(?m)^VAULT_ENCRYPTION_KEY=') {
    throw "Vault key is malformed. Restore the original key; overwriting it would permanently lock saved tokens."
  }
  $keyBytes=New-Object byte[] 32
  $rng=[System.Security.Cryptography.RandomNumberGenerator]::Create()
  try{$rng.GetBytes($keyBytes)}finally{$rng.Dispose()}
  $vaultKey=[Convert]::ToBase64String($keyBytes).Replace("+","-").Replace("/","_")
  [System.IO.File]::AppendAllText($envPath,[Environment]::NewLine+"VAULT_ENCRYPTION_KEY=$vaultKey"+[Environment]::NewLine,([System.Text.UTF8Encoding]::new($false)))
  Write-Host "Encrypted integration vault initialized; private key stored in .env." -ForegroundColor Green
}
$existing=[System.IO.File]::ReadAllText($envPath)
if ($existing -notmatch '(?m)^AUTO_REPLY_ENABLED=') {
  [System.IO.File]::AppendAllText($envPath,"AUTO_REPLY_ENABLED=false"+[Environment]::NewLine,([System.Text.UTF8Encoding]::new($false)))
}
# Record current checked-out code so the dashboard can compare it with GitHub.
$head = (& git rev-parse HEAD 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $head -notmatch '^[a-f0-9]{40}
if ($LASTEXITCODE -ne 0) { throw "Docker Compose v2 is required" }
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw "Docker build/start failed" }
Write-Host "Local dashboard: http://127.0.0.1:8787" -ForegroundColor Cyan
Write-Host "Edit .env to connect OpenAI and Meta, then run this script again." -ForegroundColor Yellow
) {
  $head="unknown"
}
$existing=[System.IO.File]::ReadAllText($envPath)
if ($existing -match '(?m)^APP_REVISION=.*
if ($LASTEXITCODE -ne 0) { throw "Docker Compose v2 is required" }
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw "Docker build/start failed" }
Write-Host "Local dashboard: http://127.0.0.1:8787" -ForegroundColor Cyan
Write-Host "Edit .env to connect OpenAI and Meta, then run this script again." -ForegroundColor Yellow
) {
  $existing=[regex]::Replace($existing,'(?m)^APP_REVISION=.*
if ($LASTEXITCODE -ne 0) { throw "Docker Compose v2 is required" }
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw "Docker build/start failed" }
Write-Host "Local dashboard: http://127.0.0.1:8787" -ForegroundColor Cyan
Write-Host "Edit .env to connect OpenAI and Meta, then run this script again." -ForegroundColor Yellow
,"APP_REVISION=$head")
} else {
  $existing += [Environment]::NewLine + "APP_REVISION=$head" + [Environment]::NewLine
}
[System.IO.File]::WriteAllText($envPath,$existing,([System.Text.UTF8Encoding]::new($false)))
docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Docker Compose v2 is required" }
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw "Docker build/start failed" }
Write-Host "Local dashboard: http://127.0.0.1:8787" -ForegroundColor Cyan
Write-Host "Edit .env to connect OpenAI and Meta, then run this script again." -ForegroundColor Yellow
