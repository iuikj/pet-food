# ============================================================
# Data migration: host (PG / Redis / MinIO) -> Docker containers
# ------------------------------------------------------------
# Prerequisites:
#   1. .env.prod is configured
#   2. Containers are up (deploy.ps1 up), at least postgres/redis/minio healthy
#   3. Host services are still running (as source of data)
#
# Usage:
#   .\deployment\migrate.ps1 pg
#   .\deployment\migrate.ps1 redis
#   .\deployment\migrate.ps1 minio
#   .\deployment\migrate.ps1 all
#
# NOTE: All strings are ASCII to stay safe under PowerShell 5.1
#       on Chinese Windows (GBK default).
# ============================================================

param(
    [Parameter(Position=0)]
    [ValidateSet('pg','redis','minio','seed','all')]
    [string]$Action = 'all',

    # PostgreSQL source
    [string]$PgSrcHost     = 'localhost',
    [int]$PgSrcPort        = 5432,
    [string]$PgSrcUser     = 'postgres',
    [string]$PgSrcPassword = 'postgres',
    [string]$PgSrcDb       = 'pet_food',

    # Redis source (password asked interactively if empty)
    [string]$RedisSrcHost = 'localhost',
    [int]$RedisSrcPort    = 6379,
    [string]$RedisSrcPassword = '',

    # MinIO source
    [string]$MinioSrcEndpoint  = 'http://localhost:9000',
    [string]$MinioSrcAccessKey = 'minioadmin',
    [string]$MinioSrcSecretKey = 'minioadmin',

    # Seed data tables (can override for more reference tables)
    [string[]]$SeedTables = @('ingredients', 'supplements'),

    [switch]$SkipBackup
)

$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$EnvFile    = Join-Path $ScriptDir '.env.prod'
$BackupDir  = Join-Path $ScriptDir ('backup_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))

function Info($m) { Write-Host "[INFO]  $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[OK]    $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[WARN]  $m" -ForegroundColor Yellow }
function Err($m)  { Write-Host "[ERR]   $m" -ForegroundColor Red }

function Get-EnvValue {
    param([string]$Key)
    if (-not (Test-Path $EnvFile)) {
        Err "$EnvFile not found. Run deploy.ps1 up first."
        exit 1
    }
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^\s*${Key}\s*=" } | Select-Object -First 1
    if (-not $line) { return '' }
    return ($line -replace "^\s*${Key}\s*=\s*", '').Trim('"', "'")
}

$ContainerPgPassword    = Get-EnvValue 'POSTGRES_PASSWORD'
$ContainerRedisPassword = Get-EnvValue 'REDIS_PASSWORD'
$ContainerMinioUser     = Get-EnvValue 'MINIO_ROOT_USER'
$ContainerMinioPassword = Get-EnvValue 'MINIO_ROOT_PASSWORD'
$ContainerMinioBucket   = Get-EnvValue 'MINIO_BUCKET'
if (-not $ContainerMinioBucket) { $ContainerMinioBucket = 'petfood-bucket' }

function Ensure-Running {
    param([string]$Container)
    $status = docker inspect -f '{{.State.Status}}' $Container 2>$null
    if ($LASTEXITCODE -ne 0 -or $status -ne 'running') {
        Err "Container $Container is not running. Run deploy.ps1 up first."
        exit 1
    }
}

function Ensure-BackupDir {
    if (-not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir | Out-Null
        Info "Backup dir: $BackupDir"
    }
}

# ────────────────────────────────────────────────────────────
#  Locate pg_dump on Windows across common / custom install paths
#  - If already in PATH -> nothing to do
#  - Else scan common roots for any PostgreSQL*\bin\pg_dump.exe
#    (C:\Program Files\, D:\, E:\DevelopFiles\, etc.)
#  - Auto-prepend found dir to $env:Path for this process only
# ────────────────────────────────────────────────────────────
function Ensure-PgDump {
    if (Get-Command pg_dump -ErrorAction SilentlyContinue) { return }

    # Roots to scan (at shallow depth for speed)
    $roots = @()
    foreach ($env_var in @('ProgramFiles', 'ProgramW6432', 'ProgramFiles(x86)')) {
        $v = (Get-Item "env:$env_var" -ErrorAction SilentlyContinue).Value
        if ($v) { $roots += $v }
    }
    # Also scan each local drive root and common dev folder names
    (Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue) | ForEach-Object {
        $d = $_.Root
        $roots += $d
        foreach ($sub in @('DevelopFiles', 'Dev', 'Tools', 'Apps')) {
            $p = Join-Path $d $sub
            if (Test-Path $p) { $roots += $p }
        }
    }
    $roots = $roots | Select-Object -Unique

    Info 'pg_dump not in PATH, scanning common install locations ...'
    $found = $null
    foreach ($root in $roots) {
        # depth=2 covers: <root>\PostgreSQL\<ver>\bin\pg_dump.exe and similar
        $match = Get-ChildItem -Path $root -Filter 'pg_dump.exe' `
                     -Recurse -Depth 3 -ErrorAction SilentlyContinue |
                 Where-Object { $_.FullName -match '(?i)postgres' } |
                 Sort-Object -Property { $_.VersionInfo.FileVersion } -Descending |
                 Select-Object -First 1
        if ($match) { $found = $match; break }
    }

    if ($found) {
        $binDir = Split-Path $found.FullName -Parent
        $env:Path = "$binDir;$env:Path"
        Ok ("Auto-detected pg_dump: " + $found.FullName)
        return
    }

    Err 'pg_dump not found anywhere.'
    Warn 'Set PATH manually (example for PG 17 in non-standard location):'
    Warn '  $env:Path = "D:\DevelopFiles\PostgreSQL_17\bin;$env:Path"'
    exit 1
}

# ============================================================
#  PostgreSQL migration
# ============================================================
function Migrate-Postgres {
    Info '========== PostgreSQL migration =========='
    Ensure-Running 'pet-food-postgres'
    Ensure-PgDump

    Ensure-BackupDir
    $dumpFile = Join-Path $BackupDir 'pg_source_dump.sql'

    Info "Dumping from host $PgSrcHost`:$PgSrcPort/$PgSrcDb ..."
    $env:PGPASSWORD = $PgSrcPassword
    try {
        & pg_dump `
            --host=$PgSrcHost `
            --port=$PgSrcPort `
            --username=$PgSrcUser `
            --dbname=$PgSrcDb `
            --no-owner `
            --no-privileges `
            --clean --if-exists `
            --file="$dumpFile"
        if ($LASTEXITCODE -ne 0) { Err 'pg_dump failed.'; exit 1 }
    }
    finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }
    $size = (Get-Item $dumpFile).Length
    Ok "Dumped: $dumpFile ($([math]::Round($size/1KB,1)) KB)"

    if (-not $SkipBackup) {
        $containerBackup = Join-Path $BackupDir 'pg_container_before.sql'
        Info 'Backing up container side before overwriting...'
        docker exec -e PGPASSWORD=$ContainerPgPassword pet-food-postgres `
            pg_dump -U petfood --no-owner --no-privileges petfood > $containerBackup 2>$null
        Ok "Container backup: $containerBackup"
    }

    Info 'Importing into container db "petfood"...'
    Get-Content $dumpFile -Raw | docker exec -i `
        -e PGPASSWORD=$ContainerPgPassword `
        pet-food-postgres psql -U petfood -d petfood -v ON_ERROR_STOP=0

    if ($LASTEXITCODE -ne 0) {
        Warn 'psql reported some errors (often role/owner related, usually safe to ignore).'
    }

    Info 'Verifying key table row counts...'
    $verify = @'
SELECT 'users' AS tbl, COUNT(*) FROM users
UNION ALL SELECT 'pets', COUNT(*) FROM pets
UNION ALL SELECT 'diet_plans', COUNT(*) FROM diet_plans
UNION ALL SELECT 'tasks', COUNT(*) FROM tasks;
'@
    $verify | docker exec -i -e PGPASSWORD=$ContainerPgPassword `
        pet-food-postgres psql -U petfood -d petfood

    Ok 'PostgreSQL migration finished.'
}

# ============================================================
#  Redis migration
# ============================================================
function Migrate-Redis {
    Info '========== Redis migration =========='
    Ensure-Running 'pet-food-redis'

    $redisCli = Get-Command redis-cli -ErrorAction SilentlyContinue
    if (-not $redisCli) {
        Warn 'redis-cli not found in PATH.'
        Warn 'Option A: install Redis for Windows and add redis-cli.exe to PATH.'
        Warn 'Option B: run the Docker one-liner:'
        Warn '  docker run --rm --network host redis:7-alpine redis-cli -h host.docker.internal -p 6379 -a <pwd> --rdb /tmp/dump.rdb'
        exit 1
    }

    if (-not $RedisSrcPassword) {
        $sec = Read-Host -Prompt 'Host Redis password (empty for no auth)' -AsSecureString
        $RedisSrcPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
        )
    }

    Ensure-BackupDir
    $rdbFile = Join-Path $BackupDir 'dump.rdb'

    Info "Dumping RDB from host $RedisSrcHost`:$RedisSrcPort ..."
    $cliArgs = @('-h', $RedisSrcHost, '-p', $RedisSrcPort)
    if ($RedisSrcPassword) { $cliArgs += @('-a', $RedisSrcPassword, '--no-auth-warning') }
    $cliArgs += @('--rdb', $rdbFile)

    & redis-cli @cliArgs
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $rdbFile)) {
        Err 'redis-cli --rdb failed.'
        exit 1
    }
    $size = (Get-Item $rdbFile).Length
    Ok "RDB dumped: $rdbFile ($([math]::Round($size/1KB,1)) KB)"

    Info 'Stopping Redis container to inject RDB ...'
    docker stop pet-food-redis | Out-Null

    Info 'Clearing old AOF inside container volume ...'
    docker run --rm -v pet-food_redis_data:/data alpine sh -c `
        'rm -rf /data/appendonlydir /data/appendonly.aof 2>/dev/null; echo cleaned'

    Info 'Copying RDB into container volume ...'
    docker cp $rdbFile pet-food-redis:/data/dump.rdb
    if ($LASTEXITCODE -ne 0) { Err 'docker cp failed.'; exit 1 }

    docker run --rm -v pet-food_redis_data:/data alpine `
        chown -R 999:1000 /data | Out-Null

    Info 'Starting Redis container ...'
    docker start pet-food-redis | Out-Null
    Start-Sleep -Seconds 3

    Info 'Verifying: DBSIZE'
    docker exec pet-food-redis redis-cli -a $ContainerRedisPassword --no-auth-warning DBSIZE

    Ok 'Redis migration finished.'
}

# ============================================================
#  Seed data migration (reference tables only, idempotent)
# ------------------------------------------------------------
#  Use case:
#    Copy curated reference data (ingredients, supplements, ...)
#    from host PG into container PG WITHOUT touching user data.
#
#  Strategy:
#    1. pg_dump --data-only --column-inserts --table=<each>
#    2. Rewrite every "INSERT ...);" -> "INSERT ...) ON CONFLICT (id) DO NOTHING;"
#    3. Wrap with session_replication_role='replica' to defer FK checks
#       (so rows referencing users not yet present just skip via ON CONFLICT)
#    4. Import via docker exec psql
#
#  Safe to re-run: existing ids are kept, only new rows are inserted.
# ============================================================
function Migrate-Seed {
    Info '========== Seed data migration =========='
    Info ("Tables: " + ($SeedTables -join ', '))
    Ensure-Running 'pet-food-postgres'
    Ensure-PgDump

    Ensure-BackupDir
    $dumpFile    = Join-Path $BackupDir 'seed_raw.sql'
    $patchedFile = Join-Path $BackupDir 'seed_patched.sql'

    # 1. Build --table args for pg_dump
    $tableArgs = @()
    foreach ($t in $SeedTables) { $tableArgs += "--table=$t" }

    Info "Dumping seed data from host $PgSrcHost`:$PgSrcPort/$PgSrcDb ..."
    $env:PGPASSWORD = $PgSrcPassword
    try {
        & pg_dump `
            --host=$PgSrcHost `
            --port=$PgSrcPort `
            --username=$PgSrcUser `
            --dbname=$PgSrcDb `
            --data-only `
            --column-inserts `
            --no-comments `
            --no-publications `
            --no-subscriptions `
            @tableArgs `
            --file="$dumpFile"
        if ($LASTEXITCODE -ne 0) { Err 'pg_dump failed.'; exit 1 }
    }
    finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }

    $raw = Get-Content $dumpFile -Raw
    if (-not $raw -or $raw.Length -lt 10) {
        Warn 'Dump is empty. Source tables may have no rows.'
        return
    }
    Info ("Dumped size: {0:N1} KB" -f ($raw.Length / 1KB))

    # 2. Strip SET lines that target-server version may not recognize.
    #    Known cross-version offenders (newer pg_dump vs older server):
    #      - transaction_timeout  (PG 17 -> PG 16 fails)
    #    Safe to drop: target psql keeps sensible defaults.
    Info 'Stripping cross-version-incompatible SET lines ...'
    $unsupportedSets = @(
        'transaction_timeout'
    )
    foreach ($name in $unsupportedSets) {
        $raw = $raw -replace "(?mi)^SET\s+${name}\s*=.*\r?\n", ''
    }

    # 3. Make each INSERT idempotent (ON CONFLICT on primary key)
    #    pg_dump --column-inserts emits one INSERT per row, ending with ');'
    Info 'Patching INSERTs to be idempotent (ON CONFLICT DO NOTHING) ...'
    $patched = [regex]::Replace(
        $raw,
        '(?ms)^(INSERT INTO [^;]+)\);\s*$',
        '$1) ON CONFLICT (id) DO NOTHING;'
    )

    # 3. Wrap with safety header/footer
    $header = @"
-- Seed import wrapped in session-level settings
BEGIN;
SET LOCAL session_replication_role = 'replica';
SET LOCAL client_min_messages = 'warning';
"@
    $footer = @"
COMMIT;
"@
    $final = $header + "`n" + $patched + "`n" + $footer
    Set-Content -Path $patchedFile -Value $final -Encoding UTF8
    Info "Patched file: $patchedFile"

    # 4. Import into container
    Info 'Importing into container DB ...'
    Get-Content $patchedFile -Raw | docker exec -i `
        -e PGPASSWORD=$ContainerPgPassword `
        pet-food-postgres psql -U petfood -d petfood -v ON_ERROR_STOP=1

    if ($LASTEXITCODE -ne 0) {
        Err 'Import failed. Check the patched SQL file for details.'
        Warn "File: $patchedFile"
        exit 1
    }

    # 5. Verify row counts
    Info 'Verifying row counts ...'
    $unionParts = @()
    foreach ($t in $SeedTables) {
        $unionParts += "SELECT '$t' AS tbl, COUNT(*) AS rows FROM $t"
    }
    $verifySql = ($unionParts -join " UNION ALL ") + ";"
    $verifySql | docker exec -i -e PGPASSWORD=$ContainerPgPassword `
        pet-food-postgres psql -U petfood -d petfood

    Ok 'Seed migration finished.'
}

# ============================================================
#  MinIO migration (mc mirror)
# ============================================================
function Migrate-Minio {
    Info '========== MinIO migration =========='
    Ensure-Running 'pet-food-minio'

    $srcUrl = $MinioSrcEndpoint -replace 'localhost', 'host.docker.internal' `
                                -replace '127\.0\.0\.1', 'host.docker.internal'

    Info "Source: $srcUrl (accessKey=$MinioSrcAccessKey)"
    Info "Target: http://minio:9000 (bucket=$ContainerMinioBucket)"

    Info 'Listing source buckets ...'
    $listScript = "mc alias set src $srcUrl $MinioSrcAccessKey $MinioSrcSecretKey --api S3v4; mc ls src;"
    $rawList = docker run --rm --add-host=host.docker.internal:host-gateway `
        minio/mc:RELEASE.2024-08-17T11-33-50Z sh -c $listScript 2>&1

    $buckets = @()
    foreach ($line in $rawList) {
        if ($line -match '\s(\S+)/\s*$') {
            $buckets += $matches[1]
        }
    }

    if (-not $buckets) {
        Warn 'No source buckets found. Either connection failed or source is empty.'
        Write-Host $rawList
        return
    }
    Info ('Source buckets: ' + ($buckets -join ', '))

    foreach ($b in $buckets) {
        Info "Mirroring bucket: $b"
        $mirrorScript = @"
mc alias set src $srcUrl $MinioSrcAccessKey $MinioSrcSecretKey --api S3v4;
mc alias set dst http://minio:9000 $ContainerMinioUser $ContainerMinioPassword --api S3v4;
mc mb --ignore-existing dst/$b;
mc mirror --overwrite src/$b dst/$b;
echo '--- target listing (first 5) ---';
mc ls dst/$b | head -5;
"@
        docker run --rm `
            --network pet-food_pet-food-network `
            --add-host=host.docker.internal:host-gateway `
            minio/mc:RELEASE.2024-08-17T11-33-50Z sh -c $mirrorScript
        if ($LASTEXITCODE -ne 0) {
            Err "Bucket $b mirror failed."
        }
    }

    Ok 'MinIO migration finished.'
}

# ============================================================
#  Main
# ============================================================
switch ($Action) {
    'pg'    { Migrate-Postgres }
    'redis' { Migrate-Redis }
    'minio' { Migrate-Minio }
    'seed'  { Migrate-Seed }
    'all'   {
        Migrate-Postgres
        Migrate-Redis
        Migrate-Minio
        Ok '========== All migrations done =========='
    }
}
