# Launch the end-user release image: full screen, no control server, chat rail.
#
# Requires the release bundle (or a Scratch 1.4 runtime) in scratch\base:
#   Scratch.exe
#   ScratchAIRelease.image / ScratchAIRelease.changes
#   Media, Help, locale, Projects
param(
    [string]$Image = "ScratchAIRelease.image"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$base = Join-Path $root "scratch\base"
$exe = Join-Path $base "Scratch.exe"
$imagePath = Join-Path $base $Image

if (-not (Test-Path $exe)) {
    throw "Scratch runtime not found at $exe.`nDownload the release bundle from GitHub Releases, or see scratch\README.md."
}
if (-not (Test-Path $imagePath)) {
    throw "Release image not found at $imagePath.`nDownload the release bundle from GitHub Releases."
}

$keyFile = Join-Path $root "bridge\.deepseek_key"
if (-not (Test-Path $keyFile) -and -not $env:DEEPSEEK_API_KEY -and -not $env:OPENCODE_GO_API_KEY) {
    Write-Warning "No API key found. Run .\setup.ps1 first, or the Bridge tab will start the offline mock bridge."
}

Write-Host "launching $Image (full screen; use File > Quit to exit)"
Start-Process -FilePath $exe `
    -ArgumentList $Image `
    -WorkingDirectory $base
