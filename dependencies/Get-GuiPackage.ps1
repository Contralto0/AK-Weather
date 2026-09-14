[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$DestinationDirectory,
    [ValidateSet('shiboken6')][string]$PackageName = 'shiboken6',
    [string]$MetadataPath,
    [scriptblock]$DownloadAction = {
        param($Uri, $OutputPath)
        Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $OutputPath
    }
)

# Windows PowerShell 5.1; lädt derzeit ausschließlich das zuerst benötigte Wheel.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$temporaryPath = $null
$result = 0

function Test-PackageFile {
    param([string]$Path, [long]$ExpectedSize, [string]$ExpectedHash)
    $stream = $null
    $hasher = $null
    try {
        $item = Get-Item -LiteralPath $Path -Force
        if ($item -isnot [System.IO.FileInfo]) { throw 'Das GUI-Paket muss eine lokale Datei sein.' }
        $stream = [System.IO.File]::Open($item.FullName, [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
        if ($stream.Length -ne $ExpectedSize) { throw 'Die Paketgroesse stimmt nicht ueberein.' }
        $hasher = [System.Security.Cryptography.SHA256]::Create()
        $actualHash = [System.BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
        if (($stream.Length -ne $ExpectedSize) -or ($actualHash -cne $ExpectedHash)) {
            throw 'Die SHA-256-Pruefsumme oder Paketgroesse stimmt nicht ueberein.'
        }
    } finally {
        if ($null -ne $hasher) { $hasher.Dispose() }
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

try {
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
    $expectedSize = $package.size_bytes
    $expectedHash = $package.sha256
    $sourceUri = $package.url
    $filename = $package.filename
    if ((($expectedSize -isnot [int]) -and ($expectedSize -isnot [long])) -or ($expectedSize -lt 0)) {
        throw 'Die erwartete Paketgroesse ist ungueltig.'
    }
    if (($expectedHash -isnot [string]) -or ($expectedHash -cnotmatch '\A[0-9a-f]{64}\z')) {
        throw 'Der erwartete SHA-256-Wert ist ungueltig.'
    }
    if (($sourceUri -isnot [string]) -or
        -not [System.Uri]::IsWellFormedUriString($sourceUri, [System.UriKind]::Absolute) -or
        ([System.Uri]$sourceUri).Scheme -cne 'https') {
        throw 'Die Downloadadresse muss eine absolute HTTPS-Adresse sein.'
    }
    if (($filename -isnot [string]) -or [string]::IsNullOrWhiteSpace($filename) -or
        ($filename -ne [System.IO.Path]::GetFileName($filename)) -or $filename.Contains(':') -or
        -not $filename.EndsWith('.whl', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Der GUI-Paketdateiname ist ungueltig.'
    }
    $deviceName = [System.IO.Path]::GetFileNameWithoutExtension($filename)
    if ($deviceName -match '\A(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])\z') {
        throw 'Der GUI-Paketdateiname ist unter Windows unzulaessig.'
    }
    $destination = Get-Item -LiteralPath $DestinationDirectory -Force
    if (($destination -isnot [System.IO.DirectoryInfo]) -or
        (($destination.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw 'Der GUI-Paketordner muss als direkter Ordner vorhanden sein.'
    }
    $destinationPath = Join-Path $destination.FullName $filename
    if (Test-Path -LiteralPath $destinationPath) {
        Test-PackageFile -Path $destinationPath -ExpectedSize $expectedSize -ExpectedHash $expectedHash
        Write-Output 'Vorhandenes GUI-Paket erfolgreich geprueft.'
    } else {
        $temporaryPath = Join-Path $destination.FullName ('.' + $filename + '.' +
            [System.Guid]::NewGuid().ToString('N') + '.partial')
        $null = & $DownloadAction ([System.Uri]$sourceUri) $temporaryPath
        Test-PackageFile -Path $temporaryPath -ExpectedSize $expectedSize -ExpectedHash $expectedHash
        [System.IO.File]::Move($temporaryPath, $destinationPath)
        $temporaryPath = $null
        Write-Output 'GUI-Paket heruntergeladen und erfolgreich geprueft.'
    }
} catch {
    [Console]::Error.WriteLine('Fehler beim Bereitstellen des GUI-Pakets: ' + $_.Exception.Message)
    $result = 1
} finally {
    if (($null -ne $temporaryPath) -and [System.IO.File]::Exists($temporaryPath)) {
        [System.IO.File]::Delete($temporaryPath)
    }
}
exit $result
