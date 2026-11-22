# Launch the end-user release image: normal window, no control server, chat rail.
#
# The image itself uses Scratch's fill-screen mode with TakeOverScreen off, so
# the Scratch frame always fills the VM client area (no turquoise World border)
# while the OS title bar and close button stay available. This script sizes and
# centres the window after launch.
#
# Requires the release bundle (or a Scratch 1.4 runtime) in scratch\base:
#   Scratch.exe
#   ScratchAIRelease.image / ScratchAIRelease.changes
#   Media, Help, locale, Projects
param(
    [string]$Image = "ScratchAIRelease.image",
    [int]$Width = 1400,
    [int]$Height = 900,
    [switch]$NoResize
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

Write-Host "launching $Image (windowed; close with the rail Quit button, File > Quit, or Alt+F4)"
$proc = Start-Process -FilePath $exe `
    -ArgumentList $Image `
    -WorkingDirectory $base `
    -PassThru

if (-not $NoResize) {
    Add-Type -AssemblyName System.Windows.Forms
    if (-not ('ScratchWindow' -as [type])) {
        Add-Type @"
using System;
using System.Runtime.InteropServices;
public class ScratchWindow {
    [DllImport("user32.dll")]
    public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);
}
"@
    }

    # Wait for the VM to create its top-level window.
    for ($i = 0; $i -lt 60; $i++) {
        $proc.Refresh()
        if ($proc.MainWindowHandle -ne [IntPtr]::Zero) { break }
        Start-Sleep -Milliseconds 200
    }
    $proc.Refresh()
    if ($proc.MainWindowHandle -ne [IntPtr]::Zero) {
        $area = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
        $w = [Math]::Max(1000, [Math]::Min($Width, $area.Width - 40))
        $h = [Math]::Max(700, [Math]::Min($Height, $area.Height - 40))
        $x = $area.Left + [int](($area.Width - $w) / 2)
        $y = $area.Top + [int](($area.Height - $h) / 2)
        [ScratchWindow]::MoveWindow($proc.MainWindowHandle, $x, $y, $w, $h, $true) | Out-Null
        Write-Host "window: ${w}x${h} at $x,$y"
    }
}
