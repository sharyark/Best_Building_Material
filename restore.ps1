# Put a backup (.dump) back into the Hisaab database, e.g. on a new PC after cloning, or to undo a mistake.
# Easiest: double-click restore.bat and pick a file, or drag a .dump file onto restore.bat.
# The database goes back to the moment of that backup: anything entered after it is removed.
# Before restoring it takes a backup of the current data (backup.ps1), so a wrong choice can be undone.

param([string]$File)

$Root = $PSScriptRoot
Set-Location $Root
$Compose = @("compose", "-f", "docker-compose.dev.yml")

function Fail($msg) {
    Write-Host ""
    Write-Host "RESTORE NAHI HUA: $msg" -ForegroundColor Red
    Write-Host "Database pehle jaisa hi hai."
    Read-Host "Press Enter to close"
    exit 1
}
function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

# ---- 1. which backup ----------------------------------------------------------------------------
if (-not $File) {
    $files = @(Get-ChildItem -Path "$Root\backups", "$Root" -Filter "*.dump" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending)
    if ($files.Count -eq 0) {
        Fail "Koi .dump file nahi mili. Backup file 'backups' folder mein (ya isi folder mein) rakhein, ya restore.bat par drag karein."
    }
    Write-Host ""
    Write-Host "Backup files (sab se nayi upar):" -ForegroundColor Cyan
    for ($i = 0; $i -lt $files.Count; $i++) {
        $f = $files[$i]
        Write-Host ("  {0,2}.  {1,-38} {2:dd-MM-yyyy HH:mm}   {3:N1} MB" -f ($i + 1), $f.Name, $f.LastWriteTime, ($f.Length / 1MB))
    }
    Write-Host ""
    $pick = Read-Host "Kaunsi file? Number likhein (khaali chhorein to band)"
    if (-not $pick) { exit 0 }
    $n = 0
    if (-not [int]::TryParse($pick, [ref]$n) -or $n -lt 1 -or $n -gt $files.Count) { Fail "Ghalat number: $pick" }
    $File = $files[$n - 1].FullName
}
if (-not (Test-Path $File)) { Fail "File nahi mili: $File" }
$File = (Resolve-Path $File).Path

# ---- 2. Docker and the database -----------------------------------------------------------------
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

# The app must not be writing while the tables are replaced.
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host ""
    Write-Host "App abhi chal rahi hai. Pehle 'Hisaab API' aur 'Hisaab Web' windows band karein." -ForegroundColor Yellow
    Read-Host "Band kar di? Enter dabayein"
    if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { Fail "'Hisaab API' window abhi bhi khuli hai. Band karke dobara chalayein." }
}

# ---- 3. check the file before touching anything -------------------------------------------------
Step "Backup file check: $(Split-Path $File -Leaf)"
docker @Compose cp "$File" db:/tmp/restore.dump *> $null
if ($LASTEXITCODE -ne 0) { Fail "File database tak nahi pahunchi." }
docker @Compose exec -T db pg_restore -l /tmp/restore.dump *> $null
if ($LASTEXITCODE -ne 0) { Fail "Ye sahi backup file nahi (ya kharab hai). Koi aur file chunein." }

# ---- 4. confirm ---------------------------------------------------------------------------------
Write-Host ""
Write-Host "DHYAN: database is backup ke waqt par wapas chala jayega:" -ForegroundColor Yellow
Write-Host "  $(Split-Path $File -Leaf)  ($('{0:dd-MM-yyyy HH:mm}' -f (Get-Item $File).LastWriteTime))"
Write-Host "Abhi database mein jo hai woh hat jayega (pehle us ka backup khud ban jayega)."
$ok = Read-Host "Pakka? 'haan' likhein"
if ($ok -ne "haan") { Write-Host "Kuch nahi badla."; Read-Host "Press Enter to close"; exit 0 }

# ---- 5. safety backup of what is there now ------------------------------------------------------
Step "Pehle abhi ke data ka backup"
& "$Root\backup.ps1" -NoPause
if ($LASTEXITCODE -ne 0) { Fail "Abhi ke data ka backup nahi bana, isliye restore roka." }

# ---- 6. restore: all or nothing -----------------------------------------------------------------
Step "Backup database mein daala ja raha hai"
docker @Compose exec -T db pg_restore -U hisaab -d hisaab --clean --if-exists --no-owner --single-transaction --exit-on-error /tmp/restore.dump
if ($LASTEXITCODE -ne 0) { Fail "Backup nahi lag saka (upar ka message dekhein)." }
docker @Compose exec -T db rm -f /tmp/restore.dump *> $null

$counts = docker @Compose exec -T db psql -tA -U hisaab -d hisaab -c "select (select count(*) from users) || ' users, ' || (select count(*) from parties) || ' customers/suppliers, ' || (select count(*) from deliveries) || ' challans'"
Write-Host ""
Write-Host "Restore ho gaya: $counts" -ForegroundColor Green
Write-Host "Ab dev_without_data.bat chalayein. Login purane system wala hoga (backup ke users)."
Read-Host "Press Enter to close"
