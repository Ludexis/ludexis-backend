# Installs the Ludexis edge device for this Windows account. Run once from the unzipped bundle:
#   powershell -ExecutionPolicy Bypass -File install.ps1
$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Dir = Join-Path $env:LOCALAPPDATA "Ludexis\edge"
$Bin = Join-Path $env:LOCALAPPDATA "Ludexis\bin"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is not installed (https://docs.docker.com/desktop/setup/install/windows-install/)."
}

New-Item -ItemType Directory -Force $Dir, $Bin, (Join-Path $Dir "state") | Out-Null
Copy-Item (Join-Path $Here "docker-compose.yml"), (Join-Path $Here ".env"), (Join-Path $Here "ludexis-edge.ps1") $Dir -Force
Copy-Item (Join-Path $Here "ludexis-edge.cmd") $Bin -Force
Get-ChildItem $Dir, $Bin -File | Unblock-File
$envFile = Join-Path $Dir ".env"
(Get-Content $envFile) -replace "^EDGE_HOSTNAME=.*", "EDGE_HOSTNAME=$env:COMPUTERNAME" | Set-Content $envFile

# ludexis-edge works in any new terminal once its folder is on this account's PATH.
$path = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not (($path -split ";") -contains $Bin)) {
    [Environment]::SetEnvironmentVariable("Path", ($path.TrimEnd(";") + ";" + $Bin).TrimStart(";"), "User")
}
$env:Path += ";$Bin"

& (Join-Path $Bin "ludexis-edge.cmd") start
Write-Host ""
Write-Host "Installed. Add a library on the server (Admin > Libraries) with this device as its location,"
Write-Host "then run: ludexis-edge restart   (also after plugging a drive in)."
