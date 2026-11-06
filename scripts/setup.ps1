<#
 Mehrad Kavir AI - safe Windows installer
 Preserves existing .env, admin credentials and database.
 Requires Windows PowerShell 5.1+, Docker Desktop and Docker Compose v2.
#>
[CmdletBinding()]
param(
    [switch]$SkipUpdateAgent,
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $ProjectRoot

function New-HexSecret([int]$ByteCount) {
    $bytes = New-Object byte[] $ByteCount
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return [BitConverter]::ToString($bytes).Replace("-", "").ToLowerInvariant()
}
function New-VaultKey {
    $bytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_")
}
function Write-PrivateText([string]$Path, [string]$Contents) {
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Contents, $encoding)
}
function Add-EnvLine([string]$Contents, [string]$Line) {
    $key = $Line.Substring(0, $Line.IndexOf("="))
    $pattern = "(?m)^" + [regex]::Escape($key) + "="
    if ($Contents -match $pattern) { return $Contents }
    if ($Contents.Length -gt 0 -and $Contents[$Contents.Length - 1] -ne [char]10) {
        $Contents += [Environment]::NewLine
    }
    return $Contents + $Line + [Environment]::NewLine
}

$EnvPath = Join-Path $ProjectRoot ".env"
$CredentialPath = Join-Path $ProjectRoot ".local-credentials.txt"
if (-not (Test-Path -LiteralPath $EnvPath)) {
    $password = New-HexSecret 24
    $verification = New-HexSecret 24
    $contents = @(
        "APP_ENV=development",
        "COOKIE_SECURE=false",
        "DB_PATH=/srv/data/mehrad.sqlite3",
        "BOOTSTRAP_ADMIN_EMAIL=admin@localhost",
        "BOOTSTRAP_ADMIN_PASSWORD=$password",
        "OPENAI_API_KEY=",
        "OPENAI_MODEL=gpt-5-mini",
        "META_APP_SECRET=",
        "META_VERIFY_TOKEN=$verification",
        "META_ACCESS_TOKEN=",
        "META_IG_USER_ID=",
        "META_GRAPH_VERSION=v25.0"
    ) -join [Environment]::NewLine
    Write-PrivateText -Path $EnvPath -Contents ($contents + [Environment]::NewLine)
    $credentials = @(
        "URL: http://127.0.0.1:8787",
        "Email: admin@localhost",
        "Password: $password"
    ) -join [Environment]::NewLine
    Write-PrivateText -Path $CredentialPath -Contents ($credentials + [Environment]::NewLine)
    Write-Host "Created .env and .local-credentials.txt with random credentials." -ForegroundColor Green
} else {
    Write-Host "Found existing .env: preserving your credentials and settings." -ForegroundColor Yellow
}

$original = [System.IO.File]::ReadAllText($EnvPath)
$contents = $original
# Never replace a pre-existing encryption key. Detect corruption early.
$vaultLines = [regex]::Matches($contents, '(?m)^VAULT_ENCRYPTION_KEY=([^\r\n]*)\r?$')
if ($vaultLines.Count -gt 1) {
    throw "Multiple VAULT_ENCRYPTION_KEY entries detected. Restore the original .env."
}
if ($vaultLines.Count -eq 1) {
    $vaultValue = $vaultLines[0].Groups[1].Value
    if ($vaultValue -notmatch '^[A-Za-z0-9_-]{43}=$') {
        throw "Existing VAULT_ENCRYPTION_KEY is invalid. It will not be replaced."
    }
} else {
    $contents = Add-EnvLine $contents ("VAULT_ENCRYPTION_KEY=" + (New-VaultKey))
    Write-Host "Created encryption key for the private integration vault." -ForegroundColor Green
}
$defaults = @(
    "AUTO_REPLY_ENABLED=false",
    "PHONE_RECEPTION_ENABLED=false",
    "AI_PROVIDER=openai"
)
foreach ($setting in $defaults) {
    $contents = Add-EnvLine $contents $setting
}

$revision = "unknown"
if (Get-Command git -ErrorAction SilentlyContinue) {
    $result = & git -C $ProjectRoot rev-parse HEAD 2>$null
    if ($LASTEXITCODE -eq 0 -and "$result" -match '^[a-f0-9]{40}$') {
        $revision = "$result"
    }
}
if ($contents -match '(?m)^APP_REVISION=') {
    $contents = [regex]::Replace($contents, '(?m)^APP_REVISION=[^\r\n]*', "APP_REVISION=$revision")
} else {
    $contents = Add-EnvLine $contents "APP_REVISION=$revision"
}
if ($contents -cne $original) { Write-PrivateText -Path $EnvPath -Contents $contents }

if (-not $SkipDocker) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker Desktop is missing or docker.exe is not on PATH."
    }
    & docker compose version
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose v2 is required. Launch Docker Desktop and retry."
    }
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop's Linux engine is not running. Open Docker Desktop first."
    }
    Write-Host "Building and starting Mehrad Kavir AI..." -ForegroundColor Cyan
    & docker compose up --build -d
    if ($LASTEXITCODE -ne 0) {
        throw "Docker build/start failed. Review the Docker error shown above."
    }
    Write-Host "Dashboard: http://127.0.0.1:8787" -ForegroundColor Green
    Write-Host "Connect Google, OpenAI and Instagram from Security & Connections." -ForegroundColor Cyan
    
}

if (-not $SkipUpdateAgent -and -not $SkipDocker) {
    $agent = Join-Path $PSScriptRoot "host-update-agent.ps1"
    if (Test-Path -LiteralPath $agent) {
        try {
            $powershellPath = Join-Path $PSHOME "powershell.exe"
            $arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $agent
            Start-Process -FilePath $powershellPath -ArgumentList $arguments -WindowStyle Hidden | Out-Null
            Write-Host "Host update agent started for owner-approved releases." -ForegroundColor DarkCyan
        } catch {
            Write-Warning "Dashboard started; update agent unavailable: $($_.Exception.Message)"
        }
    }
}
