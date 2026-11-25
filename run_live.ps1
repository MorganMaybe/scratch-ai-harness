# Launch the live model bridge.
#
# Reads the key from the environment or bridge\.deepseek_key, starts the
# opencode-go profile on 127.0.0.1:8765, and never prints the key.
#
#   .\run_live.ps1
#   .\run_live.ps1 -Profile deepseek-direct
#   .\run_live.ps1 -Audit full          # local prompt/model debugging
#   .\run_live.ps1 -Reuse               # attach to an existing bridge
#   .\run_live.ps1 -Generator dsl       # model writes Scratch-Python (json|dsl)
#   .\run_live.ps1 -History off         # disable conversation history
#   .\run_live.ps1 -StopSequence on     # DSL stop sequence (on|off; default off)
#   .\run_live.ps1 -EagerContext off    # lazy-only packs/script bodies (default on)
param(
    [switch]$DebugLog,
    [switch]$Reuse,
    [string]$LogFile,
    [string]$Profile = "opencode-go",
    [string]$Generator = "",
    [ValidateSet("", "on", "off")]
    [string]$History = "",
    [string]$StopSequence = "",
    [ValidateSet("", "on", "off")]
    [string]$EagerContext = "",
    [int]$PromptBudget = 90000,
    [ValidateSet("off", "meta", "full")]
    [string]$Audit = "off",
    [string]$AuditDir = "",
    [int]$AuditKeep = 100
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$bridge = Join-Path $root "bridge"
$keyFile = Join-Path $bridge ".deepseek_key"

# The bridge log location. -LogFile wins; otherwise the bridge's own default.
$logFileGiven = [bool]$LogFile
if (-not $logFileGiven) {
    $LogFile = Join-Path $root "scratch\base\bridge.log"
}
$LogFile = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($LogFile)
$logDir = Split-Path -Parent $LogFile
if ($logDir -and -not (Test-Path -LiteralPath $logDir)) {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
}

# Audit bundles contain prompts and raw model replies. Off by default for a
# public release; opt in while developing.
if (-not $AuditDir) {
    $AuditDir = Join-Path $root "scratch\base\audit"
}
$AuditDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($AuditDir)
if ($Audit -ne "off" -and -not (Test-Path -LiteralPath $AuditDir)) {
    New-Item -ItemType Directory -Force -Path $AuditDir | Out-Null
}

# One bridge may own 8765. Reuse a healthy one, or fail with a clear owner.
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" -ErrorAction SilentlyContinue
    $what = if ($owner) { $owner.CommandLine } else { "PID $($listener.OwningProcess)" }
    if ($Reuse) {
        Write-Host "reusing bridge already listening on 127.0.0.1:8765 ($what)"
        if ($Audit -ne "off") {
            Write-Host "note: -Audit only applies to a newly launched bridge; restart to change it."
        }
        if ($History) {
            Write-Host "note: -History only applies to a newly launched bridge; restart to change it."
        }
        if ($StopSequence) {
            Write-Host "note: -StopSequence only applies to a newly launched bridge; restart to change it."
        }
        if ($EagerContext) {
            Write-Host "note: -EagerContext only applies to a newly launched bridge; restart to change it."
        }
        exit 0
    }
    throw "port 8765 is already in use: $what`nStop that bridge first, or re-run with -Reuse to use it as-is."
}

# The key is loaded here and never printed, logged, or written to a config file.
if (-not $env:DEEPSEEK_API_KEY -and $env:OPENCODE_GO_API_KEY) {
    $env:DEEPSEEK_API_KEY = $env:OPENCODE_GO_API_KEY
}
if (-not $env:DEEPSEEK_API_KEY -and (Test-Path $keyFile)) {
    $env:DEEPSEEK_API_KEY = (Get-Content -Raw -LiteralPath $keyFile).Trim()
}
if (-not $env:DEEPSEEK_API_KEY) {
    Write-Host "DEEPSEEK_API_KEY is not set and bridge\.deepseek_key does not exist." -ForegroundColor Yellow
    Write-Host "Run .\setup.ps1 to store your own key, or set DEEPSEEK_API_KEY."
    Write-Host "For an offline test, use .\run_bridge.ps1 instead."
    exit 1
}

$env:PYTHONPATH = Join-Path $bridge "src"
if ($Generator) {
    $env:HARNESS_GENERATOR = $Generator
}
if ($History) {
    $env:HARNESS_HISTORY = $History
}
if ($StopSequence) {
    $env:HARNESS_STOP_SEQUENCE = $StopSequence
}
if ($EagerContext) {
    $env:HARNESS_EAGER_CONTEXT = $EagerContext
}
Set-Location $bridge

Write-Host "bridge profile: $Profile (key loaded, not shown)"
if ($Generator) {
    Write-Host "reply generator: $Generator"
}
if ($History) {
    Write-Host "conversation history: $History"
}
if ($EagerContext) {
    Write-Host "eager context: $EagerContext"
}
if ($StopSequence) {
    Write-Host "stop sequence: $StopSequence"
}
Write-Host "bridge log: $LogFile"
if ($Audit -ne "off") {
    Write-Host "turn audit: $Audit -> $AuditDir (prompts and raw replies are saved locally)"
}
$serverArgs = @("-u", "-m", "harness.server", "--profile", $Profile,
    "--prompt-budget", $PromptBudget, "--audit", $Audit, "--audit-keep", $AuditKeep)
if ($AuditDir -and $Audit -ne "off") {
    $serverArgs += @("--audit-dir", $AuditDir)
}
if ($logFileGiven) {
    $serverArgs += @("--log-file", $LogFile)
}
if ($DebugLog) {
    $serverArgs += @("--log-level", "DEBUG")
    Write-Host "debug logging enabled (recv/send literals)"
}
python @serverArgs
