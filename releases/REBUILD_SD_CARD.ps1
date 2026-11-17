# ==============================================================================
# REBUILD_SD_CARD.ps1 - KRISHI-DRISHTI SD card recovery tool
# ==============================================================================
# Rebuilds the KRISHI-DRISHTI MicroSD card from releases/SD_CARD_KRISHI_DRISHTI_READY.zip
# and hash-verifies the deployed model.
#
# Use this when the card:
#   - boots with "SD FAIL" on the camera
#   - reads as RAW / unrecognized filesystem on the PC
#   - was written elsewhere and must be reset to the exact release state
#
# Usage (elevated PowerShell required for format):
#   powershell -ExecutionPolicy Bypass -File REBUILD_SD_CARD.ps1 [-DriveLetter E]
#
# SAFETY: the script refuses to touch any disk that is not a small USB
# removable device (bus=USB and size <= 32GB). Nothing else can be formatted.
# ==============================================================================

param([string]$DriveLetter = "E")

$ErrorActionPreference = "Stop"
$zipPath   = Join-Path $PSScriptRoot "SD_CARD_KRISHI_DRISHTI_READY.zip"
$ModelSha  = "F48FC157CFE31C5BE979B9912433B7D7CF776F3B8743B4717DE1C9B2DC5408F1"  # round-8 deployed

"=== KRISHI-DRISHTI SD rebuild ==="

if (-not (Test-Path $zipPath)) { throw "zip not found next to this script: $zipPath" }

$p = Get-Partition -DriveLetter $DriveLetter -ErrorAction Stop
$disk = Get-Disk -Number $p.DiskNumber
"target: disk $($disk.Number) ($($disk.FriendlyName)) $([math]::Round($disk.Size/1GB,2))GB bus=$($disk.BusType)"
if ($disk.BusType -ne "USB") { throw "REFUSING: disk $($disk.Number) is not USB removable" }
if ($disk.Size -gt 32GB)     { throw "REFUSING: disk $($disk.Number) is larger than 32GB" }

"=== format FAT32 (label max 11 chars on FAT) ==="
$dpPath = Join-Path $env:TEMP "kd_rebuild_diskpart.txt"
@"
select disk $($disk.Number)
clean
create partition primary
format fs=fat32 quick label=KRISHI
assign letter=$DriveLetter
"@ | Set-Content -Path $dpPath -Encoding ASCII
$out = diskpart /s $dpPath
$out | Select-String -Pattern "succeeded|error|percent" | Select-Object -Last 6
if (-not ($out | Where-Object { $_ -match "successfully formatted" })) { throw "diskpart did not report a successful format" }
if (-not ($out | Where-Object { $_ -match "successfully assigned" }))  { throw "diskpart did not assign the drive letter" }

Start-Sleep 2
$v = Get-Volume -DriveLetter $DriveLetter
"volume $DriveLetter`: FS=$($v.FileSystem) size $([math]::Round($v.Size/1GB,2))GB"

"=== extract card image ==="
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory($zipPath, "$DriveLetter`:\")
"extracted OK"

"=== verify deployed model ==="
$h = (Get-FileHash "$DriveLetter`:\krishi_drishti_model.tflite" -Algorithm SHA256).Hash
if ($h -ne $ModelSha) { throw "MODEL HASH MISMATCH: $h (expected $ModelSha)" }
"model sha256 OK: $($h.Substring(0,16)) (round-8 deployed build)"

"=== card root ==="
Get-ChildItem "$DriveLetter`:\" -Force | ForEach-Object { "$($_.Mode)  $($_.Length)  $($_.Name)" }

""
"REBUILD COMPLETE - card ready. Remove it with 'Safely Remove Hardware', never during a write."
