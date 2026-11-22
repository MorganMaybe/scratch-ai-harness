# Build a redistributable release bundle.
#
# Requires:
#   scratch\base\Scratch.exe + the stock media tree
#   scratch\base\ScratchAIRelease.image / .changes
#   scratch\base\ScratchAiTesting.image / .changes   (unless -NoDevImage)
#
# Usage:
#   .\tools\make_release_bundle.ps1 -Version 0.1.0
#   .\tools\make_release_bundle.ps1 -Version 0.1.0 -NoDevImage
#   .\tools\make_release_bundle.ps1 -Version 0.1.0 -Force
param(
    [string]$Version = "0.1.0",
    [string]$OutDir = "release",
    [switch]$NoDevImage,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $root
$base = Join-Path $root "scratch\base"
$stage = Join-Path $root "$OutDir\ScratchAIHarness-$Version"
$zip = Join-Path $root "$OutDir\ScratchAIHarness-$Version.zip"

if (-not (Test-Path (Join-Path $base "Scratch.exe"))) {
    throw "Scratch runtime not found at $base\Scratch.exe"
}
if (-not (Test-Path (Join-Path $base "ScratchAIRelease.image"))) {
    throw "ScratchAIRelease.image not found; run .\tools\make_release_image.ps1 -Force first"
}
if (-not $NoDevImage -and -not (Test-Path (Join-Path $base "ScratchAiTesting.image"))) {
    throw "ScratchAiTesting.image not found; run .\tools\make_clean_image.ps1 or pass -NoDevImage"
}

if (Test-Path $stage) {
    if (-not $Force) { throw "$stage already exists; pass -Force to replace it" }
    Remove-Item -Recurse -Force $stage
}
New-Item -ItemType Directory -Force $stage | Out-Null

function Copy-Tree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [string[]]$ExcludeDirs = @(),
        [string[]]$ExcludeFiles = @()
    )
    New-Item -ItemType Directory -Force $Destination | Out-Null
    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        if ($_.PSIsContainer) {
            if ($ExcludeDirs -contains $_.Name) { return }
            Copy-Tree -Source $_.FullName -Destination (Join-Path $Destination $_.Name) `
                -ExcludeDirs $ExcludeDirs -ExcludeFiles $ExcludeFiles
        }
        else {
            if ($ExcludeFiles -contains $_.Name) { return }
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $Destination $_.Name)
        }
    }
}

# --- source tree ----------------------------------------------------------
$rootFiles = @(
    "README.md", "QUICKSTART.md", "TESTING.md", "CONTRIBUTING.md", "SECURITY.md",
    "RELEASE_NOTES.md", "VERSION",
    "LICENSE", "NOTICE", "TRADEMARK_POLICY", "gpl-2.0.txt", "ACKNOWLEDGEMENTS",
    "ARCHITECTURE.md", "HANDOFF.md", "CHAT_UI_SCOPE.md", "DEEPSEEK_CONNECTION_SCOPE.md",
    "SCRATCH_2_FEATURE_AUDIT.md", "SCRATCH_AI_CONTEXT.md", "SPRITE_STAGE_SCOPE.md",
    "setup.ps1", "run_release.ps1", "run_live.ps1", "run_bridge.ps1", "run_demo.ps1",
    "run_scratch.ps1"
)
foreach ($name in $rootFiles) {
    $path = Join-Path $root $name
    if (Test-Path $path) {
        Copy-Item -LiteralPath $path -Destination (Join-Path $stage $name)
    }
}

Copy-Tree -Source (Join-Path $root "bridge") -Destination (Join-Path $stage "bridge") `
    -ExcludeDirs @("__pycache__", ".pytest_cache", ".egg-info") `
    -ExcludeFiles @(".deepseek_key", "harness.ini")
Copy-Tree -Source (Join-Path $root "image") -Destination (Join-Path $stage "image") `
    -ExcludeDirs @("__pycache__")
Copy-Tree -Source (Join-Path $root "context") -Destination (Join-Path $stage "context")
Copy-Tree -Source (Join-Path $root "tools") -Destination (Join-Path $stage "tools") `
    -ExcludeDirs @("__pycache__", "media_groups_work")
New-Item -ItemType Directory -Force (Join-Path $stage "tools\media_groups_work") | Out-Null
if (Test-Path (Join-Path $root "tools\media_groups_work\merge.py")) {
    Copy-Item -LiteralPath (Join-Path $root "tools\media_groups_work\merge.py") `
        -Destination (Join-Path $stage "tools\media_groups_work\merge.py")
}
Copy-Tree -Source (Join-Path $root "docs") -Destination (Join-Path $stage "docs") `
    -ExcludeDirs @("media")
New-Item -ItemType Directory -Force (Join-Path $stage "docs\media") | Out-Null
$hero = Join-Path $root "docs\media\release-fullscreen.png"
if (Test-Path $hero) {
    Copy-Item -LiteralPath $hero -Destination (Join-Path $stage "docs\media\release-fullscreen.png")
}
Copy-Tree -Source (Join-Path $root "scratch") -Destination (Join-Path $stage "scratch") `
    -ExcludeDirs @("base")

# --- runtime --------------------------------------------------------------
$scratchStage = Join-Path $stage "scratch\base"
New-Item -ItemType Directory -Force $scratchStage | Out-Null

foreach ($name in @("Scratch.exe", "SqueakV2.sources", "Scratch.ini")) {
    Copy-Item -LiteralPath (Join-Path $base $name) -Destination (Join-Path $scratchStage $name)
}
Get-ChildItem -LiteralPath $base -Filter "*.dll" -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $scratchStage $_.Name)
}
foreach ($folder in @("Help", "locale")) {
    Copy-Tree -Source (Join-Path $base $folder) -Destination (Join-Path $scratchStage $folder)
}

Copy-Item -LiteralPath (Join-Path $base "ScratchAIRelease.image") -Destination $scratchStage
Copy-Item -LiteralPath (Join-Path $base "ScratchAIRelease.changes") -Destination $scratchStage
if (-not $NoDevImage) {
    Copy-Item -LiteralPath (Join-Path $base "ScratchAiTesting.image") -Destination $scratchStage
    Copy-Item -LiteralPath (Join-Path $base "ScratchAiTesting.changes") -Destination $scratchStage
}

# --- stock-only media -----------------------------------------------------
$excludeStems = @{}
$stemFile = Join-Path $root "tools\scratch2_only_stems.txt"
if (Test-Path $stemFile) {
    Get-Content $stemFile | ForEach-Object {
        $stem = $_.Trim().ToLowerInvariant()
        if ($stem) { $excludeStems[$stem] = $true }
    }
}
$mediaSource = Join-Path $base "Media"
$mediaDest = Join-Path $scratchStage "Media"
$mediaPattern = '^\.(png|gif|jpg|jpeg|bmp|wav|mp3|svg)$'
$mediaCount = 0
$mediaBytes = 0
Get-ChildItem -LiteralPath $mediaSource -Recurse -File | ForEach-Object {
    $file = $_
    if ($file.FullName -match '\\Scratch2\\|\\Bundles\\') { return }
    if ($file.Extension -notmatch $mediaPattern) { return }
    if ($file.Name -eq "scratchthumbs.db") { return }
    if ($excludeStems.ContainsKey($file.BaseName.ToLowerInvariant())) { return }
    $relative = $file.FullName.Substring($mediaSource.Length + 1)
    $target = Join-Path $mediaDest $relative
    New-Item -ItemType Directory -Force (Split-Path $target) | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $target
    $mediaCount++
    $mediaBytes += $file.Length
}
Write-Host "media: $mediaCount stock files ($([math]::Round($mediaBytes / 1MB, 1)) MB)"

# Remove Scratch 2.0 presets and paths that are not in the staged media.
& python (Join-Path $root "tools\release_media_groups.py") `
    (Join-Path $stage "bridge\src\harness\media_groups.json") $mediaDest
if ($LASTEXITCODE -ne 0) { throw "release media-group filter failed" }

# --- sample projects ------------------------------------------------------
$projectsSource = Join-Path $base "Projects"
$projectsDest = Join-Path $scratchStage "Projects"
New-Item -ItemType Directory -Force $projectsDest | Out-Null
Get-ChildItem -LiteralPath $projectsSource -Force | Where-Object {
    $_.Name -notin @("calculator.sb", "calculator.sb.meta", "harness-demo-text")
} | ForEach-Object {
    if ($_.PSIsContainer) {
        Copy-Tree -Source $_.FullName -Destination (Join-Path $projectsDest $_.Name)
    }
    else {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $projectsDest $_.Name)
    }
}

# --- notes ----------------------------------------------------------------
$commit = "unknown"
try { $commit = (git -C $root rev-parse --short HEAD 2>$null).Trim() } catch {}
@"
Scratch AI Harness $Version
Built:   $(Get-Date -Format 'yyyy-MM-dd HH:mm')
Commit:  $commit
Upstream: https://github.com/scratchfoundation/Scratch_1.4

Release image: ScratchAIRelease.image (full screen, no control server)
Dev image:     $(if ($NoDevImage) { 'not included' } else { 'ScratchAiTesting.image (control server on 8767)' })
Runtime:       stock Scratch 1.4 VM + stock media only
API key:       run .\setup.ps1 (stored in bridge\.deepseek_key)

This is an unofficial mod of Scratch 1.4, not affiliated with the Scratch
Foundation. See LICENSE, NOTICE and TRADEMARK_POLICY.
"@ | Set-Content -LiteralPath (Join-Path $stage "VERSION.txt") -Encoding utf8

# --- zip ------------------------------------------------------------------
New-Item -ItemType Directory -Force (Join-Path $root $OutDir) | Out-Null
if (Test-Path $zip) {
    if (-not $Force) { throw "$zip already exists; pass -Force to replace it" }
    Remove-Item -Force $zip
}
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -CompressionLevel Optimal
$size = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "built $zip ($size MB)"
