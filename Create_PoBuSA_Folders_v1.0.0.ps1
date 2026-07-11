# Create_PoBuSA_Folders_v1.0.0.ps1
# Run this once in PowerShell to set up the PoBuSA output folder structure
# under D:\Claude Downloads\, matching the pattern used for PokeBulk SA and Kudu Knitting.

$base = "D:\Claude Downloads\PoBuSA"

$folders = @(
    "$base\Backend",
    "$base\Backend\Models",
    "$base\Backend\Migrations",
    "$base\Frontend",
    "$base\Assets",
    "$base\Docs",
    "$base\Seed Data"
)

foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
        Write-Host "Created: $folder"
    } else {
        Write-Host "Already exists: $folder"
    }
}

Write-Host "`nDone. PoBuSA folder structure ready under $base"
