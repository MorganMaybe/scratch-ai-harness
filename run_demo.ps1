$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$bridge = Join-Path $root "bridge"
$env:PYTHONPATH = Join-Path $bridge "src"
Set-Location $bridge
python examples\demo.py
