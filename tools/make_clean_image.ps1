# Rebuild the maintained "latest, clean" image.
#
# The image must already be running (control server on 8767). The command:
#   1. loads image/29_clean_image.st (idempotent),
#   2. removes every script, every variable/list, and every sprite except Sprite1,
#   3. clears the harness chat, resets the AI registry/undo/ownership,
#   4. saves as -Name (default ScratchAiTesting).
#
# After the first run the VM switches to that image, so later runs clean and
# snapshot in place. Do not run it against an image another VM is using.

param(
    [string]$Name = "ScratchAiTesting",
    [switch]$SkipLoad
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not $SkipLoad) {
    $color = Join-Path $root "image\30_color_tuples.st"
    python tools\ai_control.py load $color
    $script = Join-Path $root "image\29_clean_image.st"
    python tools\ai_control.py load $script
}

python tools\ai_control.py save-clean $Name

# In-place save-clean defers the snapshot by 0.5 s so the reply is sent first;
# give it time to finish before this script exits or the VM is closed.
Start-Sleep -Milliseconds 1500
