# Backup of the whole Hisaab database (everything up to this moment) into backups\hisaab-<date>_<time>.dump.
# Easiest: double-click backup.bat. Safe to run while the app is open.
# Keeps backups for 28 days, but never fewer than the newest 4 files.
# Restore: double-click restore.bat (INSTALL.md, section 7).
# -NoPause: used by restore.ps1 for its safety backup (no "Press Enter" at the end, exit code 1 on failure).
param([switch]$NoPause)

$Root = $PSScriptRoot
Set-Location $Root
$Compose = @("compose", "-f", "docker-compose.dev.yml")
$KeepDays = 28
$KeepAtLeast = 4

function Fail($msg) {
    Write-Host ""
    Write-Host "BACKUP NAHI HUA: $msg" -ForegroundColor Red
    if (-not $NoPause) { Read-Host "Press Enter to close" }
    exit 1
}
function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail "Docker nahi mila. Docker Desktop install karein." }
docker info *> $null
if ($LASTEXITCODE -ne 0) { Fail "Docker chal nahi raha. Docker Desktop kholein, 'Engine running' ka intezar karein, phir dobara chalayein." }

Step "Database check"
docker @Compose up -d db *> $null
if ($LASTEXITCODE -ne 0) { Fail "Database start nahi hua." }
$tries = 0
do {
    Start-Sleep -Seconds 1
    docker @Compose exec -T db pg_isready -U hisaab *> $null
    $tries++
} while ($LASTEXITCODE -ne 0 -and $tries -lt 60)
if ($LASTEXITCODE -ne 0) { Fail "Database 60 second mein tayyar nahi hua." }

$Stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$Dir = Join-Path $Root "backups"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$File = Join-Path $Dir "hisaab-$Stamp.dump"

Step "Backup ban raha hai"
docker @Compose exec -T db pg_dump -U hisaab -Fc -f /tmp/hisaab-backup.dump hisaab
if ($LASTEXITCODE -ne 0) { Fail "pg_dump nakaam (upar ka message dekhein)." }
# A damaged dump is worse than none: make sure Postgres can read it back before keeping it.
docker @Compose exec -T db pg_restore -l /tmp/hisaab-backup.dump *> $null
if ($LASTEXITCODE -ne 0) { Fail "Backup file kharab bani. Dobara chalayein." }
docker @Compose cp db:/tmp/hisaab-backup.dump "$File"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $File) -or (Get-Item $File).Length -eq 0) { Fail "Backup file save nahi hui." }
docker @Compose exec -T db rm -f /tmp/hisaab-backup.dump *> $null

# Old files: older than $KeepDays, but the newest $KeepAtLeast always stay.
$all = Get-ChildItem -Path $Dir -Filter "hisaab-*.dump" | Sort-Object LastWriteTime -Descending
$old = $all | Select-Object -Skip $KeepAtLeast | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) }
foreach ($f in $old) { Remove-Item $f.FullName }

$size = "{0:N1} MB" -f ((Get-Item $File).Length / 1MB)
Write-Host ""
Write-Host "Backup ho gaya: $File ($size)" -ForegroundColor Green
if ($old) { Write-Host "Purane backup mitaye: $($old.Count) (28 din se purane)" }
Write-Host "Kul backups: $((Get-ChildItem -Path $Dir -Filter 'hisaab-*.dump').Count)  (folder: $Dir)"
Write-Host ""
if ($NoPause) { exit 0 }
Write-Host "Is file ki ek copy USB ya Google Drive par bhi rakhein."
Read-Host "Press Enter to close"
