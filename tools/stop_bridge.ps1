# Stop the local bridge on 8765 (live or mock).
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $listener) {
    Write-Host "no bridge is listening on 127.0.0.1:8765"
    exit 0
}
$owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" -ErrorAction SilentlyContinue
if ($owner) {
    Write-Host "stopping PID $($listener.OwningProcess): $($owner.CommandLine)"
} else {
    Write-Host "stopping PID $($listener.OwningProcess)"
}
Stop-Process -Id $listener.OwningProcess -Force
