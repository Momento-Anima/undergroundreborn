# Scheduled task body: mirror Discord announcements onto the website. Runs every 30 minutes (Task Scheduler, user session).
#
# WHY: Momento 2026-10-03: the News page mirrors our Discord announcements. This runs tools/mirror_announcements.py, and when
# it wrote new data it rebuilds the site and commits/pushes ONLY the news files as Phoenix.
#
# DISABLE:  schtasks /Change /TN "TUR News Mirror" /DISABLE        ENABLE: schtasks /Change /TN "TUR News Mirror" /ENABLE
# REMOVE:   schtasks /Delete /TN "TUR News Mirror" /F              RUN NOW: schtasks /Run /TN "TUR News Mirror"
# LOG:      %USERPROFILE%\.tur-bridge\news_mirror.log
# Needs this PC on and Momento's Windows login active (it uses his saved git credential, as manual pushes do).
$ErrorActionPreference = 'Continue'
$repo = 'G:\TU\undergroundreborn'
$py   = 'C:\Users\clayg\AppData\Local\Programs\Python\Python313\python.exe'
$log  = Join-Path $env:USERPROFILE '.tur-bridge\news_mirror.log'
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
function Log($m) { "$(Get-Date -Format s) $m" | Add-Content -Path $log -Encoding ascii }

Set-Location $repo
try {
    $out = & $py tools\mirror_announcements.py --warn 2>&1
    $code = $LASTEXITCODE
    foreach ($l in $out) { if ($l -match 'WARNING|mirrored|error|Traceback') { Log "$l" } }
    if ($code -eq 2) {
        & $py build.py | Out-Null
        git add data/news.json assets/news news/index.html 2>&1 | Out-Null
        git diff --cached --quiet -- data assets/news news
        if ($LASTEXITCODE -ne 0) {
            git commit -q --author="Phoenix <phoenix@momentoanima.com>" -m "News: mirror new Discord announcement(s) (automatic)" -m "Co-Authored-By: MomentoAnima <clay@momentoanima.com>`nCo-Authored-By: Phoenix <phoenix@momentoanima.com>" -- data/news.json assets/news news/index.html 2>&1 | Out-Null
            git pull -q --rebase --autostash 2>&1 | Out-Null
            git push -q 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Log 'pushed new announcement(s)' } else { Log 'PUSH FAILED' }
        } else { Log 'changed data but nothing staged' }
    } elseif ($code -ne 0) { Log "mirror script exit code $code" }
} catch { Log "EXCEPTION: $($_.Exception.Message)" }
