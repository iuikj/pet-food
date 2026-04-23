# ============================================================
# Pet Food Assistant - Windows PowerShell deployment helper
# ------------------------------------------------------------
# Usage:
#   .\deployment\deploy.ps1 up
#   .\deployment\deploy.ps1 logs api
#   .\deployment\deploy.ps1 down
#
# NOTE: All messages are in ASCII to stay safe under PowerShell 5.1
#       on Chinese Windows (GBK default). Chinese docs live in README.
# ============================================================

param(
    [Parameter(Position=0)]
    [ValidateSet('up','down','clean','logs','restart','ps','status','migrate','shell')]
    [string]$Action = 'up',

    [Parameter(Position=1)]
    [string]$Service = ''
)

$ErrorActionPreference = 'Stop'

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir  = Split-Path -Parent $ScriptDir
$ComposeFile = Join-Path $ScriptDir 'docker-compose.prod.yml'
$EnvFile     = Join-Path $ScriptDir '.env.prod'

function Info($msg)  { Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "[OK]    $msg" -ForegroundColor Green }
function Warn($msg)  { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Err($msg)   { Write-Host "[ERR]   $msg" -ForegroundColor Red }

function Preflight {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Err 'Docker Desktop is not installed or not in PATH.'
        exit 1
    }

    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) {
        Err 'docker compose v2 is not available.'
        exit 1
    }

    # Probe daemon: pipe/socket is only present when Docker Desktop is fully up.
    Info 'Checking Docker daemon ...'
    $null = docker info --format '{{.ServerVersion}}' 2>&1
    if ($LASTEXITCODE -ne 0) {
        Err 'Cannot reach Docker daemon.'
        Warn 'Open Docker Desktop and wait until the tray icon shows "Engine running".'
        Warn 'Verify with: docker info'
        Warn 'If Docker Desktop is already open, it might still be starting (WSL backend can take 30-60s).'
        exit 1
    }

    if (-not (Test-Path $EnvFile)) {
        Err "Missing env file: $EnvFile"
        Warn "Run: Copy-Item $ScriptDir\.env.prod.example $EnvFile  then edit it."
        exit 1
    }

    if (Select-String -Path $EnvFile -Pattern 'CHANGE_ME' -Quiet) {
        Err '.env.prod still contains CHANGE_ME placeholders. Replace them first.'
        Select-String -Path $EnvFile -Pattern 'CHANGE_ME' | Select-Object -First 5
        exit 1
    }

    # Validate that every required key has a non-empty value
    $requiredKeys = @(
        'POSTGRES_PASSWORD', 'REDIS_PASSWORD',
        'MINIO_ROOT_USER', 'MINIO_ROOT_PASSWORD',
        'JWT_SECRET_KEY', 'SECRET_KEY',
        'DASHSCOPE_API_KEY', 'TAVILIY_API_KEY'
    )
    $missing = @()
    foreach ($key in $requiredKeys) {
        $line = Get-Content $EnvFile | Where-Object { $_ -match "^\s*${key}\s*=" } | Select-Object -First 1
        if (-not $line) { $missing += "$key (not present)"; continue }
        $value = ($line -replace "^\s*${key}\s*=\s*", '').Trim('"', "'").Trim()
        if (-not $value) { $missing += "$key (empty value)" }
    }
    if ($missing.Count -gt 0) {
        Err 'Missing or empty required env keys:'
        $missing | ForEach-Object { Write-Host ('  - ' + $_) -ForegroundColor Red }
        Warn 'Edit .env.prod and fill these in. For values with special chars, wrap in single quotes.'
        exit 1
    }
}

function Compose {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$ComposeArgs)
    & docker compose --project-directory $ProjectDir -f $ComposeFile --env-file $EnvFile @ComposeArgs
}

switch ($Action) {
    'up' {
        Preflight
        Info 'Building images (first build may take several minutes)...'
        Compose build --pull
        if ($LASTEXITCODE -ne 0) { Err 'Build failed.'; exit 1 }

        Info 'Starting services...'
        Compose up -d
        if ($LASTEXITCODE -ne 0) {
            Err 'Service startup failed. Likely causes:'
            Warn '  - Postgres volume mismatch (data dir initialized by a different PG version)'
            Warn '  - Port 80 / 9000 / 9001 already in use on host'
            Warn '  - Required env var missing in .env.prod'
            Warn ''
            Warn 'Quick diagnosis:'
            Warn '  .\deployment\deploy.ps1 logs postgres    # check db init errors'
            Warn '  .\deployment\deploy.ps1 ps               # see which service is unhealthy'
            exit 1
        }

        Start-Sleep -Seconds 5
        Compose ps

        # Verify core services are actually running (not crashing on loop)
        $failed = @()
        foreach ($svc in @('postgres', 'redis', 'minio', 'api', 'frontend', 'nginx')) {
            $state = docker inspect -f '{{.State.Status}}' "pet-food-$svc" 2>$null
            if ($LASTEXITCODE -ne 0 -or $state -ne 'running') {
                $failed += "$svc (state=$state)"
            }
        }

        Write-Host ''
        if ($failed.Count -gt 0) {
            Err 'Some services are not running:'
            $failed | ForEach-Object { Write-Host ('  - ' + $_) -ForegroundColor Red }
            Warn 'Check logs: .\deployment\deploy.ps1 logs <service>'
            exit 1
        }

        Ok 'All services healthy. Entrypoints:'
        Write-Host '    Frontend   : http://localhost'
        Write-Host '    API docs   : http://localhost/docs'
        Write-Host '    Health     : http://localhost/health'
        Write-Host '    MinIO UI   : http://localhost:9001'
        Write-Host ''
        Write-Host "View logs: .\deployment\deploy.ps1 logs"
    }

    'down' {
        Info 'Stopping services (volumes kept)...'
        Compose down
        Ok 'Stopped.'
    }

    'clean' {
        Warn 'This will DELETE all persistent data (PostgreSQL / Redis / MinIO volumes)!'
        $confirm = Read-Host 'Type YES to confirm'
        if ($confirm -ne 'YES') { Info 'Cancelled.'; return }
        Compose down -v
        Ok 'Cleaned.'
    }

    'logs' {
        if ($Service) { Compose logs -f --tail=200 $Service }
        else          { Compose logs -f --tail=100 }
    }

    'restart' {
        Compose restart
        Compose ps
    }

    { $_ -in 'ps','status' } {
        Compose ps
        Write-Host ''
        Info 'Resource usage:'
        $raw = Compose ps -q
        $ids = ($raw -split "`n") | Where-Object { $_ -and $_.Trim() }
        if ($ids) {
            docker stats --no-stream --format "table {{.Name}}`t{{.CPUPerc}}`t{{.MemUsage}}`t{{.MemPerc}}" @ids
        }
    }

    'migrate' {
        Info 'Running Alembic migrations...'
        Compose exec api alembic upgrade head
        Ok 'Migration done.'
    }

    'shell' {
        $svc = if ($Service) { $Service } else { 'api' }
        Compose exec $svc sh
    }
}
