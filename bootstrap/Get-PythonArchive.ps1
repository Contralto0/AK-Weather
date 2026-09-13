[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$DestinationPath,
    [string]$MetadataPath,
    [scriptblock]$DownloadAction = {
        param($Uri, $OutputPath)
        Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $OutputPath
    }
)

# Windows PowerShell 5.1; kein Python-Aufruf und keine Entpackung.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$temporaryPath = $null
$result = 0

function Test-ArchiveFile {
    param([string]$Path, [long]$ExpectedSize, [string]$ExpectedHash)
    $stream = $null
    $hasher = $null
    try {
        $item = Get-Item -LiteralPath $Path -Force
        if ($item -isnot [System.IO.FileInfo]) { throw 'Das Archiv muss eine lokale Datei sein.' }
        $stream = [System.IO.File]::Open($item.FullName, [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
        if ($stream.Length -ne $ExpectedSize) { throw 'Die Archivgroesse stimmt nicht ueberein.' }
        $hasher = [System.Security.Cryptography.SHA256]::Create()
        $actualHash = [System.BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
        if (($stream.Length -ne $ExpectedSize) -or ($actualHash -cne $ExpectedHash)) {
            throw 'Die SHA-256-Pruefsumme oder Archivgroesse stimmt nicht ueberein.'
        }
    } finally {
        if ($null -ne $hasher) { $hasher.Dispose() }
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

try {
    if (-not $PSBoundParameters.ContainsKey('MetadataPath')) {
        $scriptDirectory = [System.IO.Path]::GetDirectoryName($MyInvocation.MyCommand.Path)
        $MetadataPath = Join-Path $scriptDirectory 'windows-python.lock.json'
    }
    $metadataFile = Get-Item -LiteralPath $MetadataPath -Force
    if ($metadataFile -isnot [System.IO.FileInfo]) { throw 'Der Python-Datensatz muss eine lokale Datei sein.' }
    $spec = ConvertFrom-Json -InputObject ([System.IO.File]::ReadAllText($metadataFile.FullName))
    if (($spec -isnot [pscustomobject]) -or ($spec.format_version -ne 1) -or
        ($spec.archive -isnot [pscustomobject])) { throw 'Der Python-Datensatz hat ein ungueltiges Format.' }
    $expectedSize = $spec.archive.size_bytes
    $expectedHash = $spec.archive.sha256
    $sourceUri = $spec.archive.url
    if ((($expectedSize -isnot [int]) -and ($expectedSize -isnot [long])) -or ($expectedSize -lt 0)) {
        throw 'Die erwartete Archivgroesse ist ungueltig.'
    }
    if (($expectedHash -isnot [string]) -or ($expectedHash -cnotmatch '\A[0-9a-f]{64}\z')) {
        throw 'Der erwartete SHA-256-Wert ist ungueltig.'
    }
    if (($sourceUri -isnot [string]) -or -not [System.Uri]::IsWellFormedUriString($sourceUri, [System.UriKind]::Absolute) -or
        ([System.Uri]$sourceUri).Scheme -cne 'https') { throw 'Die Downloadadresse muss eine absolute HTTPS-Adresse sein.' }

    $destinationFullPath = [System.IO.Path]::GetFullPath($DestinationPath)
    if (Test-Path -LiteralPath $destinationFullPath) {
        Test-ArchiveFile -Path $destinationFullPath -ExpectedSize $expectedSize -ExpectedHash $expectedHash
        Write-Output 'Vorhandenes Python-Archiv erfolgreich geprueft.'
    } else {
        $destinationDirectory = [System.IO.Path]::GetDirectoryName($destinationFullPath)
        if (-not [System.IO.Directory]::Exists($destinationDirectory)) {
            throw 'Der Zielordner fuer das Python-Archiv fehlt.'
        }
        $temporaryPath = Join-Path $destinationDirectory ('.' + [System.IO.Path]::GetFileName($destinationFullPath) +
            '.' + [System.Guid]::NewGuid().ToString('N') + '.partial')
        $null = & $DownloadAction ([System.Uri]$sourceUri) $temporaryPath
        Test-ArchiveFile -Path $temporaryPath -ExpectedSize $expectedSize -ExpectedHash $expectedHash
        [System.IO.File]::Move($temporaryPath, $destinationFullPath)
        $temporaryPath = $null
        Write-Output 'Python-Archiv heruntergeladen und erfolgreich geprueft.'
    }
} catch {
    [Console]::Error.WriteLine('Fehler beim Bereitstellen des Python-Archivs: ' + $_.Exception.Message)
    $result = 1
} finally {
    if (($null -ne $temporaryPath) -and [System.IO.File]::Exists($temporaryPath)) {
        [System.IO.File]::Delete($temporaryPath)
    }
}
exit $result
