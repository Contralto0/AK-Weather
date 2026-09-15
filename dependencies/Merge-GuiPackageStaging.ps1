[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$ShibokenStagingPath,
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$EssentialsStagingPath,
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$DestinationPath
)

# Windows PowerShell 5.1; verbindet zwei bereits sicher entpackte Paketordner.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$destinationCreated = $false
$completed = $false
$result = 0

try {
    $sourcePaths = @(
        [System.IO.Path]::GetFullPath($ShibokenStagingPath),
        [System.IO.Path]::GetFullPath($EssentialsStagingPath)
    )
    if ([string]::Equals($sourcePaths[0], $sourcePaths[1],
            [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Die beiden Paket-Stagingordner müssen verschieden sein.'
    }
    $destinationFullPath = [System.IO.Path]::GetFullPath($DestinationPath)
    if (Test-Path -LiteralPath $destinationFullPath) {
        throw 'Der gemeinsame Anwendungs-Stagingordner darf noch nicht existieren.'
    }
    $destinationParent = [System.IO.Path]::GetDirectoryName($destinationFullPath)
    if (-not [System.IO.Directory]::Exists($destinationParent)) {
        throw 'Der Elternordner des gemeinsamen Stagingziels fehlt.'
    }
    $destinationPrefix = $destinationFullPath.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $targets = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase)
    $entries = [System.Collections.Generic.List[object]]::new()

    foreach ($sourcePath in $sourcePaths) {
        $source = Get-Item -LiteralPath $sourcePath -Force
        if (($source -isnot [System.IO.DirectoryInfo]) -or
            (($source.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw 'Jede Paketquelle muss ein normaler lokaler Ordner sein.'
        }
        $sourcePrefix = $source.FullName.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
        if ($destinationFullPath.StartsWith($sourcePrefix,
                [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Das gemeinsame Stagingziel darf nicht innerhalb einer Paketquelle liegen.'
        }
        foreach ($item in Get-ChildItem -LiteralPath $source.FullName -Force -Recurse) {
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Verknüpfungen sind im Paket-Staging nicht erlaubt: $($item.FullName)"
            }
            if (($item -isnot [System.IO.FileInfo]) -and ($item -isnot [System.IO.DirectoryInfo])) {
                throw "Unbekannter Eintrag im Paket-Staging: $($item.FullName)"
            }
            $relative = $item.FullName.Substring($sourcePrefix.Length)
            if ([string]::IsNullOrWhiteSpace($relative) -or (-not $targets.Add($relative))) {
                throw "Mehrdeutiger Paket-Zielpfad: $relative"
            }
            $target = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($destinationFullPath, $relative))
            if (-not $target.StartsWith($destinationPrefix,
                    [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Paket-Eintrag liegt außerhalb des gemeinsamen Stagingordners: $relative"
            }
            $entries.Add([pscustomobject]@{
                Source = $item.FullName
                Target = $target
                Directory = ($item -is [System.IO.DirectoryInfo])
            })
        }
    }

    [System.IO.Directory]::CreateDirectory($destinationFullPath) | Out-Null
    $destinationCreated = $true
    foreach ($entry in $entries) {
        if ($entry.Directory) {
            [System.IO.Directory]::CreateDirectory($entry.Target) | Out-Null
            continue
        }
        [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($entry.Target)) | Out-Null
        $inputStream = $null
        $outputStream = $null
        try {
            $inputStream = [System.IO.File]::Open($entry.Source, [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
            $outputStream = [System.IO.File]::Open($entry.Target, [System.IO.FileMode]::CreateNew,
                [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
            $inputStream.CopyTo($outputStream)
        } finally {
            if ($null -ne $outputStream) { $outputStream.Dispose() }
            if ($null -ne $inputStream) { $inputStream.Dispose() }
        }
    }
    $completed = $true
    Write-Output 'GUI-Paket-Stagingordner sicher zusammengeführt.'
} catch {
    [Console]::Error.WriteLine('Fehler beim Zusammenführen der GUI-Pakete: ' + $_.Exception.Message)
    $result = 1
} finally {
    if ($destinationCreated -and -not $completed -and
        [System.IO.Directory]::Exists($destinationFullPath)) {
        [System.IO.Directory]::Delete($destinationFullPath, $true)
    }
}
exit $result
