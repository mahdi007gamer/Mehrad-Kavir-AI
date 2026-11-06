# Mehrad Kavir AI host update agent — Windows ONLY.
# Runs under the signed-in Windows user, outside Docker. Never accepts
# URLs, paths, shell code or commands from AI/customer messages.
$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot
$createdNew = $false
$mutex = New-Object System.Threading.Mutex($true,"Local\MehradKavirAIUpdater",[ref]$createdNew)
if (-not $createdNew) { exit 0 }

function Invoke-Tool([string]$exe,[string[]]$argv) {
  $out = & $exe @argv 2>&1
  if ($LASTEXITCODE -ne 0) { throw "$exe exited with code $LASTEXITCODE" }
  return ($out | Out-String).Trim()
}

function Apply-Update($ticket) {
  $sha = [string]$ticket.target_sha
  $id = [string]$ticket.id
  if ($sha -notmatch '^[a-f0-9]{40}$' -or $id -notmatch '^\d+$') { return }
  $old = ""
  $originalEnv = $null
  $changedGit = $false
  try {
    $origin = Invoke-Tool "git" @("remote","get-url","origin")
    if ($origin -ne "https://github.com/mahdi007gamer/Mehrad-Kavir-AI.git" -and
        $origin -ne "git@github.com:mahdi007gamer/Mehrad-Kavir-AI.git") {
      throw "Repository origin does not match allowlisted Mehrad-Kavir-AI"
    }
    $dirty = Invoke-Tool "git" @("status","--porcelain")
    if ($dirty) { throw "Working tree contains local changes; refusing unattended deployment" }
    $claim = Invoke-Tool "docker" @("compose","exec","-T","web","python","-m","app.update_ticket","claim",$id,$sha)
    if (-not (($claim | ConvertFrom-Json).ok)) { throw "Update ticket already handled" }
    $old = Invoke-Tool "git" @("rev-parse","HEAD")
    $null = Invoke-Tool "git" @("fetch","--quiet","origin","main")
    $upstream = Invoke-Tool "git" @("rev-parse","FETCH_HEAD")
    if ($sha -ne $upstream) { throw "Approved SHA differs from official main; no update performed" }
    $null = Invoke-Tool "git" @("merge-base","--is-ancestor",$old,$sha)
    $null = Invoke-Tool "docker" @("compose","exec","-T","web","python","-m","app.update_ticket","backup")
    $originalEnv = [System.IO.File]::ReadAllText((Join-Path $ProjectRoot ".env"))
    $null = Invoke-Tool "git" @("merge","--ff-only","FETCH_HEAD")
    $changedGit = $true
    $envText = $originalEnv
    if ($envText -match '(?m)^APP_REVISION=.*$') {
      $envText = [regex]::Replace($envText,'(?m)^APP_REVISION=.*$',"APP_REVISION=$sha")
    } else {
      $envText += [Environment]::NewLine + "APP_REVISION=$sha" + [Environment]::NewLine
    }
    [System.IO.File]::WriteAllText((Join-Path $ProjectRoot ".env"),$envText,([System.Text.UTF8Encoding]::new($false)))
    $null = Invoke-Tool "docker" @("compose","up","--build","-d")
    Start-Sleep -Seconds 5
    $health = Invoke-Tool "docker" @("compose","exec","-T","web","python","-m","app.update_ticket","finish",$id,$sha,"completed")
    if (-not (($health | ConvertFrom-Json).ok)) { throw "Update status could not be confirmed" }
  } catch {
    # Restore local code and environment if deployment failed.
    if ($changedGit -and $old -match '^[a-f0-9]{40}$') {
      try { $null = Invoke-Tool "git" @("reset","--hard",$old) } catch {}
    }
    if ($null -ne $originalEnv) {
      try { [System.IO.File]::WriteAllText((Join-Path $ProjectRoot ".env"),$originalEnv,([System.Text.UTF8Encoding]::new($false))) } catch {}
    }
    try { $null = Invoke-Tool "docker" @("compose","up","--build","-d") } catch {}
    try {
      $null = Invoke-Tool "docker" @("compose","exec","-T","web","python","-m","app.update_ticket","finish",$id,$sha,"failed","Update failed; inspect host logs")
    } catch {}
  }
}

try {
  while ($true) {
    try {
      Set-Location $ProjectRoot
      $raw = Invoke-Tool "docker" @("compose","exec","-T","web","python","-m","app.update_ticket","peek")
      $ticket = $raw | ConvertFrom-Json
      if ($ticket -and $ticket.id -and $ticket.target_sha) {
        Apply-Update $ticket
      }
    } catch {
      # Docker Desktop may be offline. Never run updates without valid ticket.
    }
    Start-Sleep -Seconds 25
  }
} finally {
  if ($createdNew) { $mutex.ReleaseMutex() }
  $mutex.Dispose()
}
