# Ludexis edge device for Windows: ludexis-edge start | restart | stop | status | logs | update
param([Parameter(Position = 0)][string]$Command = "help")

$ErrorActionPreference = "Stop"
$Dir = Join-Path $env:LOCALAPPDATA "Ludexis\edge"
Set-Location $Dir

function Invoke-Compose { docker compose --project-name ludexis-edge @args }

function Get-EnvValue([string]$Name) {
    $line = Get-Content (Join-Path $Dir ".env") | Where-Object { $_ -match "^$Name=" } | Select-Object -Last 1
    if ($line) { return $line.Substring($Name.Length + 1).Trim() }
    return ""
}

# Linux shows an NTFS drive's 64-bit serial and Windows its low 32 bits; both end in the same 8 hex digits.
function Get-DriveKey([string]$Id) {
    $plain = ($Id -replace "-", "").ToLower()
    if ($plain.Length -gt 8) { return $plain.Substring($plain.Length - 8) }
    return $plain
}

function Wait-Docker {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) { return }
    $desktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $desktop)) { throw "Docker is not running and Docker Desktop was not found." }
    Write-Host "Starting Docker Desktop..."
    Start-Process $desktop
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 2
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { return }
    }
    throw "Docker Desktop did not start within two minutes."
}

# Docker Desktop's VM mounts only the drives that existed when it started; a drive plugged in or unlocked later
# (USB, VeraCrypt) would be bound as an empty folder. Mount it into the VM now, or remount it if it went stale.
function Mount-DockerDrive([string]$Letter) {
    $path = "/mnt/host/$($Letter.ToLower())"
    wsl.exe -d docker-desktop -u root sh -c "{ mountpoint -q $path && ls $path; } >/dev/null 2>&1 || { umount -l $path 2>/dev/null; mkdir -p $path && mount -t drvfs ${Letter}: $path; } >/dev/null 2>&1"
    if ($LASTEXITCODE -ne 0) { Write-Warning "Could not make drive ${Letter}: visible to Docker Desktop; restart Docker Desktop with the drive connected." }
}

# Finds the drive letter of every library of this device (by serial once it was scanned, else by the letter in its
# path), maps those letters into the container and records their serials for it.
function Update-Drives {
    $server = (Get-EnvValue "LUDEXIS_SERVER_URL").TrimEnd("/")
    $token = Get-EnvValue "LUDEXIS_EDGE_TOKEN"
    try {
        # Windows PowerShell returns a JSON array as one object; ForEach-Object unrolls it into its items.
        $libraries = @(Invoke-RestMethod -Uri "$server/api/edge/agent/libraries" -Headers @{ Authorization = "Bearer $token" } -TimeoutSec 15 | ForEach-Object { $_ })
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        if ($code -eq 401) { throw "The server refused this device's token; download a new bundle from Admin > Edge." }
        Write-Warning "Server $server is not reachable ($($_.Exception.Message)); keeping the current drive mapping."
        return
    }

    $volumes = @(Get-CimInstance Win32_Volume | Where-Object { $_.DriveLetter -and $_.SerialNumber })
    $mapped = [ordered]@{}
    foreach ($library in $libraries) {
        $volume = $null
        if ($library.drive_id) {
            $wanted = Get-DriveKey $library.drive_id
            $volume = $volumes | Where-Object { (Get-DriveKey ("{0:x8}" -f [uint32]$_.SerialNumber)) -eq $wanted } | Select-Object -First 1
        }
        if (-not $volume -and $library.path -match "^([A-Za-z]):") {
            $letter = $Matches[1].ToUpper()
            $volume = $volumes | Where-Object { $_.DriveLetter -eq "${letter}:" } | Select-Object -First 1
        }
        if ($volume) {
            $letter = $volume.DriveLetter.Substring(0, 1).ToUpper()
            $mapped[$letter] = @{ serial = ("{0:X8}" -f [uint32]$volume.SerialNumber); label = $volume.Label }
            Write-Host ("Library    {0} ({1}): drive {2}: found" -f $library.name, $library.path, $letter)
        } else {
            Write-Host ("Library    {0} ({1}): drive not connected" -f $library.name, $library.path)
        }
    }

    New-Item -ItemType Directory -Force (Join-Path $Dir "state") | Out-Null
    # Written without a byte order mark, which Windows PowerShell would otherwise add.
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [IO.File]::WriteAllText((Join-Path $Dir "state\drives.json"), ($mapped | ConvertTo-Json -Depth 3), $utf8)
    $lines = @("# Written by ludexis-edge restart from the libraries on the server; do not edit.", "services:", "  edge:", "    volumes:")
    foreach ($letter in $mapped.Keys) {
        Mount-DockerDrive $letter
        $lines +="      - type: bind", "        source: '${letter}:\'", "        target: /drives/$letter", "        read_only: true"
    }
    if ($mapped.Count -eq 0) { $lines = $lines[0..2] + "    volumes: []" }
    [IO.File]::WriteAllLines((Join-Path $Dir "docker-compose.override.yml"), [string[]]$lines, $utf8)
}

function Show-Status {
    Invoke-Compose ps
    for ($i = 0; $i -lt 10; $i++) {
        Invoke-Compose exec -T edge true *> $null
        if ($LASTEXITCODE -eq 0) { break }
        Start-Sleep -Seconds 1
    }
    Invoke-Compose exec -T edge python -m app.edge.status
}

switch ($Command) {
    "start" { Wait-Docker; Update-Drives; Invoke-Compose up -d }
    "restart" { Wait-Docker; Update-Drives; Invoke-Compose up -d --force-recreate; Show-Status }
    "stop" { Invoke-Compose stop }
    "status" { Wait-Docker; Show-Status }
    "logs" { Invoke-Compose logs -f --tail 100 }
    "update" { Wait-Docker; Invoke-Compose pull; Update-Drives; Invoke-Compose up -d --force-recreate; Show-Status }
    default {
        Write-Host @"
ludexis-edge start    start the edge device (starts Docker Desktop if needed)
ludexis-edge restart  check Docker, the server and the drives, map the drive letters, recreate the container
ludexis-edge stop     stop it; waiting scans run when it starts again
ludexis-edge status   the server connection and, per library, whether its drive is here
ludexis-edge logs     follow its log
ludexis-edge update   pull the newest image and restart

After plugging a drive in or unlocking an encrypted volume, run "ludexis-edge restart": it makes the drive
visible to Docker Desktop and maps it into the container. Mapped network drives are not visible to Docker Desktop.
"@
    }
}
