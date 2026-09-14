[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$ArchivePath,
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$DestinationPath
)

# Windows PowerShell 5.1; nur ein zuvor geprueftes lokales ZIP entpacken.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$archive = $null
$archiveStream = $null
$destinationCreated = $false
$completed = $false
$result = 0

try {
    Add-Type -AssemblyName System.IO.Compression
    $archiveFile = Get-Item -LiteralPath $ArchivePath -Force
    if ($archiveFile -isnot [System.IO.FileInfo]) {
        throw 'Das Archiv muss eine lokale Datei sein.'
    }

    $destinationFullPath = [System.IO.Path]::GetFullPath($DestinationPath)
    if (Test-Path -LiteralPath $destinationFullPath) {
        throw 'Das temporaere Ziel darf noch nicht existieren.'
    }
    $destinationParent = [System.IO.Path]::GetDirectoryName($destinationFullPath)
    if (-not [System.IO.Directory]::Exists($destinationParent)) {
        throw 'Der Elternordner des temporaeren Ziels fehlt.'
    }
    $rootPrefix = $destinationFullPath.TrimEnd([System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar

    # Der offene Handle verhindert eine Aenderung zwischen Pruefung und Entpackung.
    $archiveStream = [System.IO.File]::Open($archiveFile.FullName, [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    $archive = [System.IO.Compression.ZipArchive]::new($archiveStream,
        [System.IO.Compression.ZipArchiveMode]::Read, $false)
    $targets = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase)
    $validated = [System.Collections.Generic.List[object]]::new()

    foreach ($entry in $archive.Entries) {
        $name = $entry.FullName.Replace('\', '/')
        if ([string]::IsNullOrWhiteSpace($name) -or $name.StartsWith('/') -or
            $name.StartsWith('//') -or $name.Contains(':')) {
            throw "Unsicherer ZIP-Pfad: $($entry.FullName)"
        }
        $isDirectory = $name.EndsWith('/')
        $parts = $name.TrimEnd('/').Split('/')
        if (($parts.Count -eq 0) -or ($parts -contains '') -or ($parts -contains '.') -or
            ($parts -contains '..')) {
            throw "Unsicherer ZIP-Pfad: $($entry.FullName)"
        }
        foreach ($part in $parts) {
            $deviceName = $part.Split('.')[0]
            if ($part.EndsWith(' ') -or $part.EndsWith('.') -or
                ($deviceName -match '\A(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])\z')) {
                throw "Unter Windows unzulaessiger ZIP-Pfad: $($entry.FullName)"
            }
        }
        $unixType = (($entry.ExternalAttributes -shr 16) -band 0xF000)
        $isReparsePoint = (($entry.ExternalAttributes -band 0x400) -ne 0)
        if (($unixType -eq 0xA000) -or $isReparsePoint) {
            throw "Verknuepfungen sind im Python-ZIP nicht erlaubt: $($entry.FullName)"
        }

        $target = $destinationFullPath
        foreach ($part in $parts) { $target = [System.IO.Path]::Combine($target, $part) }
        $target = [System.IO.Path]::GetFullPath($target)
        if (-not $target.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "ZIP-Eintrag liegt ausserhalb des Zielordners: $($entry.FullName)"
        }
        if (-not $targets.Add($target)) {
            throw "Mehrdeutiger ZIP-Zielpfad: $($entry.FullName)"
        }
        $validated.Add([pscustomobject]@{ Entry = $entry; Target = $target; Directory = $isDirectory })
    }

    [System.IO.Directory]::CreateDirectory($destinationFullPath) | Out-Null
    $destinationCreated = $true
    foreach ($item in $validated) {
        if ($item.Directory) {
            [System.IO.Directory]::CreateDirectory($item.Target) | Out-Null
            continue
        }
        $parent = [System.IO.Path]::GetDirectoryName($item.Target)
        [System.IO.Directory]::CreateDirectory($parent) | Out-Null
        $inputStream = $null
        $outputStream = $null
        try {
            $inputStream = $item.Entry.Open()
            $outputStream = [System.IO.File]::Open($item.Target, [System.IO.FileMode]::CreateNew,
                [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
            $inputStream.CopyTo($outputStream)
        } finally {
            if ($null -ne $outputStream) { $outputStream.Dispose() }
            if ($null -ne $inputStream) { $inputStream.Dispose() }
        }
    }
    $completed = $true
    Write-Output 'Python-Archiv sicher in das temporaere Ziel entpackt.'
} catch {
    [Console]::Error.WriteLine('Fehler beim Entpacken des Python-Archivs: ' + $_.Exception.Message)
    $result = 1
} finally {
    if ($null -ne $archive) { $archive.Dispose() }
    if ($null -ne $archiveStream) { $archiveStream.Dispose() }
    if ($destinationCreated -and -not $completed -and
        [System.IO.Directory]::Exists($destinationFullPath)) {
        [System.IO.Directory]::Delete($destinationFullPath, $true)
    }
}
exit $result
