param(
    [string]$Image = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$scratch = Join-Path $root "scratch\base"
if (-not (Test-Path (Join-Path $scratch "Scratch.exe"))) {
    throw "Scratch VM not found at $scratch\Scratch.exe"
}

if ($Image -eq "") {
    $names = @(
        "ScratchAiTesting.image",
        "ScratchAIRelease.image",
        "ScratchAI11.image",
        "ScratchAI10.image",
        "ScratchAI9.image",
        "ScratchDev.image",
        "ScratchAI8.image",
        "Scratch.image"
    )
    foreach ($name in $names) {
        if (Test-Path (Join-Path $scratch $name)) {
            $Image = $name
            break
        }
    }
}
if ($Image -eq "") {
    throw "no Scratch image found in $scratch"
}

$imagePath = if ([System.IO.Path]::IsPathRooted($Image)) { $Image } else { Join-Path $scratch $Image }
if (-not (Test-Path $imagePath)) {
    throw "image not found: $imagePath"
}

# A dev image reads scratch\base\harness.ini at startup. Create a local one so
# a fresh bundle never opens Squeak's file chooser for a missing config.
$config = Join-Path $scratch "harness.ini"
if (-not (Test-Path $config)) {
    @"
# Created by run_scratch.ps1. Git-ignored; edit locally.
devMode=on
autoOpen=off
autoSnapshot=off
snapshotEvery=10
errors=$scratch\dev_errors.log
controlServer=on
bridgeLaunch=auto
"@ | Set-Content -LiteralPath $config -Encoding ascii
}

# Squeak splits the argument list on spaces, so pass a bare/relative image name
# and use its folder as the working directory instead of an absolute path.
$workDir = $scratch
$imageArg = $Image
if ([System.IO.Path]::IsPathRooted($Image)) {
    $workDir = Split-Path -Parent $imagePath
    $imageArg = Split-Path -Leaf $imagePath
}
Write-Host "launching $imageArg (working directory $workDir)"
Start-Process -FilePath (Join-Path $scratch "Scratch.exe") `
    -ArgumentList $imageArg `
    -WorkingDirectory $workDir
