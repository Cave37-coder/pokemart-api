<#
.SYNOPSIS
    PokeBulk SA - Rename Bible Folders to DB (TCGCSV) Codes
    v3.0.0
    Reads mapping from master_set_mapping_v2.csv
    Uses tcgio_code column to find bible folders
    Renames to db_code
    Run with -DryRun first!
.EXAMPLE
    .\rename-bible-to-db-codes-v3.0.0.ps1 -DryRun
    .\rename-bible-to-db-codes-v3.0.0.ps1
#>

param(
    [switch]$DryRun = $false,
    [string]$MappingCsv = "C:\Users\texca\pokemart-api\File dump from Downloads\master_set_mapping_v2.csv",
    [string]$BibleDir = "D:\Card Pics"
)

Write-Host ""
Write-Host "=============================================="
Write-Host "PokeBulk SA - Bible Rename v3.0.0"
Write-Host "Mapping CSV : $MappingCsv"
Write-Host "Bible Dir   : $BibleDir"
Write-Host "Dry Run     : $DryRun"
Write-Host "=============================================="
Write-Host ""

# Build mapping from master_set_mapping_v2.csv
Write-Host "Reading mapping from master_set_mapping_v2.csv..."

$mapping = @{}  # tcgio_code -> db_code
$allRows = Import-Csv $MappingCsv

foreach ($row in $allRows) {
    $dbCode   = $row.db_code.Trim()
    $tcgioCode = $row.tcgio_code.Trim()

    if ($tcgioCode -and $dbCode -and -not $mapping.ContainsKey($tcgioCode)) {
        $mapping[$tcgioCode] = $dbCode
    }
}

Write-Host "  Found $($mapping.Count) tcgio -> db_code mappings"
Write-Host ""

# Show mapping
Write-Host "Mappings:"
$mapping.GetEnumerator() | Sort-Object Key | ForEach-Object {
    Write-Host "  $($_.Key) -> $($_.Value)"
}
Write-Host ""

# Rename folders and files
$renamed   = 0
$skipped   = 0
$errors    = 0
$notMapped = @()

$folders = Get-ChildItem $BibleDir -Directory | Sort-Object Name

foreach ($folder in $folders) {
    $tcgioCode = $folder.Name

    if (-not $mapping.ContainsKey($tcgioCode)) {
        Write-Host "WARNING: No mapping for: $tcgioCode"
        $notMapped += $tcgioCode
        continue
    }

    $dbCode        = $mapping[$tcgioCode]
    $newFolderPath = Join-Path $BibleDir $dbCode

    if ($tcgioCode -eq $dbCode) {
        Write-Host "OK: $tcgioCode (already correct)"
        $skipped++
        continue
    }

    if (Test-Path $newFolderPath) {
        Write-Host "SKIP: $tcgioCode -> $dbCode (target already exists)"
        $skipped++
        continue
    }

    Write-Host "RENAME: $tcgioCode -> $dbCode"

    if (-not $DryRun) {
        try {
            # Rename files inside folder first
            $files = Get-ChildItem $folder.FullName -Filter "*.jpg"
            $fileRenamed = 0
            foreach ($file in $files) {
                $newFileName = $file.Name -replace "^${tcgioCode}_", "${dbCode}_"
                if ($file.Name -ne $newFileName) {
                    $newFilePath = Join-Path $folder.FullName $newFileName
                    Rename-Item $file.FullName $newFilePath -ErrorAction Stop
                    $fileRenamed++
                }
            }
            Write-Host "  Renamed $fileRenamed files"

            # Rename the folder
            Rename-Item $folder.FullName $newFolderPath -ErrorAction Stop
            $renamed++
        } catch {
            Write-Host "  ERROR: $_"
            $errors++
        }
    } else {
        $fileCount = (Get-ChildItem $folder.FullName -Filter "*.jpg").Count
        Write-Host "  Would rename $fileCount files"
        $renamed++
    }
}

Write-Host ""
Write-Host "=============================================="
if ($DryRun) {
    Write-Host "DRY RUN - no changes saved"
} else {
    Write-Host "DONE!"
}
Write-Host "  Renamed  : $renamed folders"
Write-Host "  Skipped  : $skipped"
Write-Host "  Errors   : $errors"
if ($notMapped.Count -gt 0) {
    Write-Host "  Not mapped: $($notMapped -join ', ')"
}
Write-Host "=============================================="
