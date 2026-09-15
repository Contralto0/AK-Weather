[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$WheelPath,
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$DestinationPath,
    [ValidateSet('shiboken6', 'PySide6-Essentials')][string]$PackageName = 'shiboken6',
    [string]$MetadataPath
)

# Windows PowerShell 5.1; prüft und entpackt die festgelegten GUI-Pakete.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$stream = $null
$archive = $null
$hasher = $null
$destinationCreated = $false
$completed = $false
$result = 0

try {
    Add-Type -AssemblyName System.IO.Compression
    if (-not $PSBoundParameters.ContainsKey('MetadataPath')) {
        $scriptDirectory = [System.IO.Path]::GetDirectoryName($MyInvocation.MyCommand.Path)
        $MetadataPath = Join-Path $scriptDirectory 'windows-gui.lock.json'
    }
    $metadataFile = Get-Item -LiteralPath $MetadataPath -Force
    if ($metadataFile -isnot [System.IO.FileInfo]) { throw 'Der GUI-Datensatz muss eine lokale Datei sein.' }
    $spec = ConvertFrom-Json -InputObject ([System.IO.File]::ReadAllText($metadataFile.FullName))
    if (($spec -isnot [pscustomobject]) -or ($spec.format_version -ne 1) -or
        ($null -eq $spec.packages)) { throw 'Der GUI-Datensatz hat ein ungueltiges Format.' }
    $matches = @($spec.packages | Where-Object { $_.name -ceq $PackageName })
    if ($matches.Count -ne 1) { throw 'Das festgelegte GUI-Paket fehlt oder ist nicht eindeutig.' }
    $package = $matches[0]
    if ((($package.size_bytes -isnot [int]) -and ($package.size_bytes -isnot [long])) -or
        ($package.size_bytes -lt 0) -or ($package.sha256 -isnot [string]) -or
        ($package.sha256 -cnotmatch '\A[0-9a-f]{64}\z')) {
        throw 'Die Prüfwerte des GUI-Pakets sind ungueltig.'
    }

    $wheelFile = Get-Item -LiteralPath $WheelPath -Force
    if (($wheelFile -isnot [System.IO.FileInfo]) -or
        ($wheelFile.Name -cne $package.filename)) {
        throw 'Das Wheel muss die festgelegte lokale Paketdatei sein.'
    }
    $destinationFullPath = [System.IO.Path]::GetFullPath($DestinationPath)
    if (Test-Path -LiteralPath $destinationFullPath) { throw 'Das Paket-Stagingziel darf noch nicht existieren.' }
    $destinationParent = [System.IO.Path]::GetDirectoryName($destinationFullPath)
    if (-not [System.IO.Directory]::Exists($destinationParent)) {
        throw 'Der Elternordner des Paket-Stagingziels fehlt.'
    }
    $rootPrefix = $destinationFullPath.TrimEnd([System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar

    $stream = [System.IO.File]::Open($wheelFile.FullName, [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    if ($stream.Length -ne $package.size_bytes) { throw 'Die Wheel-Groesse stimmt nicht ueberein.' }
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    $actualHash = [System.BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    if (($stream.Length -ne $package.size_bytes) -or ($actualHash -cne $package.sha256)) {
        throw 'Die SHA-256-Pruefsumme oder Wheel-Groesse stimmt nicht ueberein.'
    }
    $stream.Position = 0
    $archive = [System.IO.Compression.ZipArchive]::new($stream,
        [System.IO.Compression.ZipArchiveMode]::Read, $true)
    $targets = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase)
    $validated = [System.Collections.Generic.List[object]]::new()

    foreach ($entry in $archive.Entries) {
        $name = $entry.FullName.Replace('\', '/')
        if ([string]::IsNullOrWhiteSpace($name) -or $name.StartsWith('/') -or $name.Contains(':')) {
            throw "Unsicherer Wheel-Pfad: $($entry.FullName)"
        }
        $isDirectory = $name.EndsWith('/')
        $parts = $name.TrimEnd('/').Split('/')
        if (($parts.Count -eq 0) -or ($parts -contains '') -or ($parts -contains '.') -or
            ($parts -contains '..')) { throw "Unsicherer Wheel-Pfad: $($entry.FullName)" }
        foreach ($part in $parts) {
            $deviceName = $part.Split('.')[0]
            if ($part.EndsWith(' ') -or $part.EndsWith('.') -or
                ($deviceName -match '\A(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])\z')) {
                throw "Unter Windows unzulaessiger Wheel-Pfad: $($entry.FullName)"
            }
        }
        $unixType = (($entry.ExternalAttributes -shr 16) -band 0xF000)
        if (($unixType -eq 0xA000) -or (($entry.ExternalAttributes -band 0x400) -ne 0)) {
            throw "Verknuepfungen sind im Wheel nicht erlaubt: $($entry.FullName)"
        }
        $target = $destinationFullPath
        foreach ($part in $parts) { $target = [System.IO.Path]::Combine($target, $part) }
        $target = [System.IO.Path]::GetFullPath($target)
        if (-not $target.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Wheel-Eintrag liegt ausserhalb des Stagingordners: $($entry.FullName)"
        }
        if (-not $targets.Add($target)) { throw "Mehrdeutiger Wheel-Zielpfad: $($entry.FullName)" }
        $validated.Add([pscustomobject]@{ Entry = $entry; Target = $target; Directory = $isDirectory })
    }

    [System.IO.Directory]::CreateDirectory($destinationFullPath) | Out-Null
    $destinationCreated = $true
    foreach ($item in $validated) {
        if ($item.Directory) {
            [System.IO.Directory]::CreateDirectory($item.Target) | Out-Null
            continue
        }
        [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($item.Target)) | Out-Null
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
    Write-Output "$PackageName-Wheel sicher in den Paket-Stagingordner entpackt."
} catch {
    [Console]::Error.WriteLine('Fehler beim Entpacken des GUI-Pakets: ' + $_.Exception.Message)
    $result = 1
} finally {
    if ($null -ne $archive) { $archive.Dispose() }
    if ($null -ne $hasher) { $hasher.Dispose() }
    if ($null -ne $stream) { $stream.Dispose() }
    if ($destinationCreated -and -not $completed -and [System.IO.Directory]::Exists($destinationFullPath)) {
        [System.IO.Directory]::Delete($destinationFullPath, $true)
    }
}
exit $result
