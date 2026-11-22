# One-time setup for the Scratch AI Harness.
#
#   .\setup.ps1                 # runtime install + API key prompt
#   .\setup.ps1 -Dev            # also install pytest and editable bridge
#   .\setup.ps1 -Key "..."      # non-interactive key (avoid shell history)
#   .\setup.ps1 -Profile deepseek-direct
#
# The key is written to bridge\.deepseek_key, which is git-ignored. It is never
# printed, logged or placed in the Squeak image.
param(
    [string]$Key = "",
    [switch]$Dev,
    [string]$Profile = "",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$bridge = Join-Path $root "bridge"
$keyFile = Join-Path $bridge ".deepseek_key"
$iniFile = Join-Path $bridge "harness.ini"
$iniExample = Join-Path $bridge "harness.ini.example"

Write-Host "Scratch AI Harness setup"
Write-Host "repository: $root"

# --- Python ---------------------------------------------------------------
$python = "python"
& $python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.11 or newer is required on PATH. Install it from https://www.python.org/downloads/ and re-run setup."
}
$version = (& $python -c "import sys; print(sys.version.split()[0])").Trim()
Write-Host "python: $version"

if (-not $SkipInstall) {
    Write-Host "installing bridge dependencies..."
    Push-Location $bridge
    try {
        if ($Dev) {
            & $python -m pip install -e ".[dev]"
        }
        else {
            & $python -m pip install -e "."
        }
        if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    }
    finally {
        Pop-Location
    }
}

# --- Bridge profile -------------------------------------------------------
if (-not (Test-Path $iniFile)) {
    Copy-Item -LiteralPath $iniExample -Destination $iniFile
    Write-Host "created bridge\harness.ini from the example"
}
if ($Profile) {
    $content = Get-Content -LiteralPath $iniFile -Raw
    $content = $content -replace '(?m)^default=.*$', "default=$Profile"
    Set-Content -LiteralPath $iniFile -Value $content.TrimEnd() -Encoding ascii
    Write-Host "default bridge profile: $Profile"
}

# --- API key --------------------------------------------------------------
if (-not $Key) {
    if ($env:OPENCODE_GO_API_KEY) {
        $Key = $env:OPENCODE_GO_API_KEY
    }
    elseif ($env:DEEPSEEK_API_KEY) {
        $Key = $env:DEEPSEEK_API_KEY
    }
}

if (-not $Key -and -not (Test-Path $keyFile)) {
    Write-Host ""
    Write-Host "Paste your API key. It is masked and stored only in bridge\.deepseek_key."
    Write-Host "The default profile is '$(if ($Profile) { $Profile } else { 'opencode-go' })'."
    $secure = Read-Host -AsSecureString "API key"
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $Key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

if ($Key) {
    $clean = $Key.Trim()
    if (-not $clean) { throw "the API key is empty" }
    Set-Content -LiteralPath $keyFile -Value $clean -NoNewline -Encoding ascii
    Write-Host "saved API key to bridge\.deepseek_key (never commit this file)"
}
elseif (Test-Path $keyFile) {
    Write-Host "using the existing bridge\.deepseek_key"
}
else {
    Write-Warning "No API key yet. Live chat will not work until you run setup again or set DEEPSEEK_API_KEY."
}

Write-Host ""
Write-Host "Next steps:"
if (Test-Path (Join-Path $root "scratch\base\ScratchAIRelease.image")) {
    Write-Host "  .\run_release.ps1          # launch the full-screen release image"
}
else {
    Write-Host "  Download the release bundle from GitHub Releases, or run .\run_scratch.ps1"
}
Write-Host "  Bridge tab -> Start        # starts the local model bridge"
Write-Host "  .\run_bridge.ps1           # offline mock bridge instead"
if ($Dev) {
    Write-Host "  cd bridge; python -m pytest -q"
}
