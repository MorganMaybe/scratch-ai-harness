$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$bridge = Join-Path $root "bridge"

$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" -ErrorAction SilentlyContinue
    $what = if ($owner) { $owner.CommandLine } else { "PID $($listener.OwningProcess)" }
    throw "port 8765 is already in use: $what`nStop that bridge first, or use it as-is."
}

$env:PYTHONPATH = Join-Path $bridge "src"
Set-Location $bridge
python -u examples\run_mock_server.py
