[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$ArchivePath,
    [string]$MetadataPath
)

# Windows PowerShell 5.1; ausschliesslich lokale Dateien lesen, kein Python-Aufruf.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$stream = $null
$hasher = $null
$result = 0
try {
    if (-not $PSBoundParameters.ContainsKey('MetadataPath')) {
        $scriptDirectory = [System.IO.Path]::GetDirectoryName($MyInvocation.MyCommand.Path)
        $MetadataPath = Join-Path $scriptDirectory 'windows-python.lock.json'
    }
    $metadataFile = Get-Item -LiteralPath $MetadataPath -Force
    if ($metadataFile -isnot [System.IO.FileInfo]) {
        throw 'Der Python-Datensatz muss eine lokale Datei sein.'
    }
    $spec = ConvertFrom-Json -InputObject ([System.IO.File]::ReadAllText($metadataFile.FullName))
    if (($spec -isnot [pscustomobject]) -or
        (($spec.format_version -isnot [int]) -and ($spec.format_version -isnot [long])) -or
        ($spec.format_version -ne 1) -or ($spec.archive -isnot [pscustomobject])) {
        throw 'Der Python-Datensatz hat ein ungueltiges Format.'
    }
    $expectedSize = $spec.archive.size_bytes
    $expectedHash = $spec.archive.sha256
    if ((($expectedSize -isnot [int]) -and ($expectedSize -isnot [long])) -or
        ($expectedSize -lt 0)) {
        throw 'Die erwartete Archivgroesse muss eine nichtnegative Ganzzahl sein.'
    }
    if (($expectedHash -isnot [string]) -or ($expectedHash -cnotmatch '\A[0-9a-f]{64}\z')) {
        throw 'Der erwartete SHA-256-Wert ist ungueltig.'
    }
    $archiveFile = Get-Item -LiteralPath $ArchivePath -Force
    if ($archiveFile -isnot [System.IO.FileInfo]) {
        throw 'Das Archiv muss eine lokale Datei sein.'
    }
    # Derselbe offene Handle dient beiden Pruefungen; Windows sperrt Schreib-/Loeschzugriffe.
    $stream = [System.IO.File]::Open($archiveFile.FullName, [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    if ($stream.Length -ne $expectedSize) {
        throw 'Die Archivgroesse stimmt nicht mit dem Datensatz ueberein.'
    }
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    $actualHash = [System.BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    if (($stream.Length -ne $expectedSize) -or ($actualHash -cne $expectedHash)) {
        throw 'Die SHA-256-Pruefsumme oder Archivgroesse stimmt nicht ueberein.'
    }
    Write-Output 'Python-Archiv erfolgreich geprueft.'
} catch {
    [Console]::Error.WriteLine('Fehler bei der Python-Archivpruefung: ' + $_.Exception.Message)
    $result = 1
} finally {
    if ($null -ne $hasher) { $hasher.Dispose() }
    if ($null -ne $stream) { $stream.Dispose() }
}
exit $result
