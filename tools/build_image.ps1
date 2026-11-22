# Build the Scratch AI harness image from image/*.st.
#
# The seed must already contain the dev loader (ScratchAiTesting or later). The build
# copies the seed to a scratch name, launches it, loads 00_bootstrap.st through
# the control server, then saves the result as <Out>.image/.changes.
#
# Usage:
#   .\tools\build_image.ps1
#   .\tools\build_image.ps1 -Out ScratchDev2 -Seed ScratchAI9 -Force
param(
    [string]$Seed = "ScratchAiTesting",
    [string]$Out = "ScratchDev",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $root
$base = Join-Path $root "scratch\base"
$exe = Join-Path $base "Scratch.exe"
$python = "python"

if (-not (Test-Path $exe)) {
    throw "Scratch VM not found at $exe"
}

$seedImage = Join-Path $base "$Seed.image"
$seedChanges = Join-Path $base "$Seed.changes"
if (-not (Test-Path $seedImage) -or -not (Test-Path $seedChanges)) {
    throw "seed image not found: $seedImage / $seedChanges"
}

$outImage = Join-Path $base "$Out.image"
$outChanges = Join-Path $base "$Out.changes"
if ((Test-Path $outImage) -and -not $Force) {
    throw "$outImage already exists; pass -Force to replace it"
}
if ($Force) {
    Remove-Item -Force $outImage, $outChanges -ErrorAction SilentlyContinue
}

$listener = Get-NetTCPConnection -LocalPort 8767 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "port 8767 is already serving a Scratch image; close it before building"
}

$buildName = "ScratchBuild"
$buildImage = Join-Path $base "$buildName.image"
$buildChanges = Join-Path $base "$buildName.changes"
Remove-Item -Force $buildImage, $buildChanges -ErrorAction SilentlyContinue
Copy-Item -Force $seedImage $buildImage
Copy-Item -Force $seedChanges $buildChanges

$proc = Start-Process -FilePath $exe `
    -ArgumentList "$buildName.image" `
    -WorkingDirectory $base `
    -PassThru

try {
    & $python (Join-Path $root "tools\wait_control.py") | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "the build image did not start its control server"
    }

    $install = & $python (Join-Path $root "tools\ai_control.py") load 00_bootstrap.st
    $install | Out-Host
    if ($install -like "error:*") {
        throw "bootstrap install failed: $install"
    }

    $bootstrap = & $python (Join-Path $root "tools\ai_control.py") bootstrap
    $bootstrap | Out-Host
    if ($bootstrap -like "error:*") {
        throw "bootstrap failed: $bootstrap"
    }

    $save = & $python (Join-Path $root "tools\ai_control.py") save $Out
    $save | Out-Host
    if ($save -like "error:*") {
        throw "save failed: $save"
    }
}
finally {
    if ($proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force
    }
    Remove-Item -Force $buildImage, $buildChanges -ErrorAction SilentlyContinue
}

if (-not (Test-Path $outImage) -or -not (Test-Path $outChanges)) {
    throw "build did not produce $outImage and $outChanges"
}
Write-Host "built $outImage"
