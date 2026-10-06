# Scheduled task body: copy the live events file to the website's private admin store. Meant to run every 2 minutes (Task Scheduler, user session).
#
# WHY: Momento 2026-10-06: the admin map gets an Events layer, "as long as we're not putting a burden on the game server".
# So this does ONE read-only SFTP copy of ONE small file (no directory listing, no write to the game server), and only POSTs it to the Worker when
# it changed or 10 minutes passed. The game server writes the file on change anyway; it never knows this task exists.
#
# DRY RUN (default): fetches and prints size + md5 + a few fields; posts to the TEST key only when -Post is given.
#   powershell -File tools\events_feed_task.ps1                 (dry run, no post)
#   powershell -File tools\events_feed_task.ps1 -Post -Feed test (post to events:test)
#   powershell -File tools\events_feed_task.ps1 -Post -Feed live (post to events:latest; only after TheConductor says live)
# DISABLE:  schtasks /Change /TN "TUR Events Feed" /DISABLE      REMOVE: schtasks /Delete /TN "TUR Events Feed" /F
# LOG:      %USERPROFILE%\.tur-bridge\events_feed.log
# SECRET:   %USERPROFILE%\.tur-bridge\events_ingest.json  {"secret": "<INGEST_SECRET>"}   (outside the repo; never commit, never print)
param([switch]$Post, [ValidateSet('test','live')][string]$Feed = 'test')
$ErrorActionPreference = 'Continue'
$rc     = 'C:\Users\clayg\AppData\Local\rclone\rclone-v1.75.0-windows-amd64\rclone.exe'
$remote = 'tu:DayZServerData/TUR/EventsAdmin/state.json'
$api    = 'https://api.theundergroundserver.com'
$dir    = Join-Path $env:USERPROFILE '.tur-bridge'
$log    = Join-Path $dir 'events_feed.log'
$stateF = Join-Path $dir ("events_feed_state_$Feed.json")
$tmp    = Join-Path $env:TEMP 'tur_events_state.json'
New-Item -ItemType Directory -Force $dir | Out-Null
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content -Path $log -Encoding ascii }

try {
    if (Test-Path $tmp) { Remove-Item $tmp -Force }
    & $rc copyto $remote $tmp --sftp-set-modtime=false 2>&1 | Out-Null
    if (-not (Test-Path $tmp)) { Log 'fetch failed (no file)'; Write-Output 'fetch failed'; exit 1 }
    $size = (Get-Item $tmp).Length
    if ($size -gt 32000) { Log "file too large ($size bytes), not sent"; Write-Output "too large: $size"; exit 1 }
    $md5 = (Get-FileHash $tmp -Algorithm MD5).Hash
    $last = $null
    if (Test-Path $stateF) { try { $last = Get-Content $stateF -Raw | ConvertFrom-Json } catch {} }
    $ageMin = if ($last) { ((Get-Date) - [datetime]$last.at).TotalMinutes } else { 999 }
    $changed = (-not $last) -or ($last.md5 -ne $md5)
    Write-Output "fetched $size bytes, md5 $md5, changed=$changed, minutes since last post=$([math]::Round($ageMin,1))"
    if (-not $Post) { Write-Output 'dry run: nothing posted'; exit 0 }
    if (-not $changed -and $ageMin -lt 10) { exit 0 }
    $secFile = Join-Path $dir 'events_ingest.json'
    if (-not (Test-Path $secFile)) { Log 'no secret file, not posted'; Write-Output 'no secret file'; exit 1 }
    $secret = (Get-Content $secFile -Raw | ConvertFrom-Json).secret
    $body = [System.IO.File]::ReadAllBytes($tmp)
    $q = if ($Feed -eq 'test') { '?feed=test' } else { '' }
    $r = Invoke-WebRequest -Uri "$api/ingest/events$q" -Method Post -Body $body -ContentType 'application/json' -Headers @{ 'X-Ingest-Secret' = $secret } -UseBasicParsing
    @{ md5 = $md5; at = (Get-Date).ToString('s') } | ConvertTo-Json | Set-Content -Path $stateF -Encoding ascii
    Log "posted $size bytes to $Feed, status $($r.StatusCode)"
    Write-Output "posted, status $($r.StatusCode)"
} catch { Log "EXCEPTION: $($_.Exception.Message)"; Write-Output "error: $($_.Exception.Message)"; exit 1 }
