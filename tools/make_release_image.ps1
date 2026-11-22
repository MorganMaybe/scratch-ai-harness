# Build a release (end-user) image from a clean harness image.
#
# The source image must have the harness classes and the dev loader. The build
# copies it to a temporary name, launches it, loads image/40_release_image.st,
# saves a clean, full-screen image with the 8767 control server disabled, then
# stops the build VM.
#
# Usage:
#   .\tools\make_release_image.ps1
#   .\tools\make_release_image.ps1 -Source ScratchAiTesting -Out ScratchAIRelease -Force
param(
    [string]$Source = "ScratchAiTesting",
    [string]$Out = "ScratchAIRelease",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $root
$base = Join-Path $root "scratch\base"
$exe = Join-Path $base "Scratch.exe"

if (-not (Test-Path $exe)) {
    throw "Scratch VM not found at $exe. Install the Scratch 1.4 runtime first."
}

$sourceImage = Join-Path $base "$Source.image"
$sourceChanges = Join-Path $base "$Source.changes"
if (-not (Test-Path $sourceImage) -or -not (Test-Path $sourceChanges)) {
    throw "source image not found: $sourceImage / $sourceChanges"
}

$outImage = Join-Path $base "$Out.image"
$outChanges = Join-Path $base "$Out.changes"
if ((Test-Path $outImage) -and -not $Force) {
    throw "$outImage already exists; pass -Force to replace it"
}

$listener = Get-NetTCPConnection -LocalPort 8767 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "port 8767 is already serving a Scratch image; close it before building"
}

$buildName = "ScratchReleaseBuild"
$buildImage = Join-Path $base "$buildName.image"
$buildChanges = Join-Path $base "$buildName.changes"
Remove-Item -Force $buildImage, $buildChanges -ErrorAction SilentlyContinue
Copy-Item -Force $sourceImage $buildImage
Copy-Item -Force $sourceChanges $buildChanges

$proc = Start-Process -FilePath $exe `
    -ArgumentList "$buildName.image" `
    -WorkingDirectory $base `
    -PassThru

try {
    & python (Join-Path $root "tools\wait_control.py") | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "the build image did not start its control server"
    }

    # Refresh the portable paths, safe file checks, command handler and
    # release-mode methods. Source edits are not in an older seed.
    $releaseFiles = @(
        "17c_loader_fix.st",
        "16b_safe_control.st",
        "22_dev_config.st",
        "38_bridge_usage_ui.st",
        "29_clean_image.st",
        "40_release_image.st"
    )
    foreach ($releaseFile in $releaseFiles) {
        $load = & python (Join-Path $root "tools\ai_control.py") load $releaseFile
        $load | Out-Host
        if ($load -like "error:*") {
            throw "$releaseFile load failed: $load"
        }
    }

    $save = & python (Join-Path $root "tools\ai_control.py") release-save $Out
    $save | Out-Host
    if ($save -like "error:*") {
        throw "release save failed: $save"
    }
}
finally {
    # release-save forks a 0.5 s snapshot; let it finish before stopping the VM.
    Start-Sleep -Milliseconds 2000
    if ($proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force
    }
    Remove-Item -Force $buildImage, $buildChanges -ErrorAction SilentlyContinue
}

if (-not (Test-Path $outImage) -or -not (Test-Path $outChanges)) {
    throw "release build did not produce $outImage and $outChanges"
}
Write-Host "built release image $outImage"
