[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$StagingPath,
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$RuntimeRootPath,
    [string]$MetadataPath
)

# Windows PowerShell 5.1; kein Python-Aufruf, Download oder Entpacken.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$result = 0

function Test-SingleWindowsName {
    param([object]$Value, [string]$Description)
    if (($Value -isnot [string]) -or [string]::IsNullOrWhiteSpace($Value) -or
        ($Value -ne [System.IO.Path]::GetFileName($Value)) -or $Value.Contains(':') -or
        $Value.EndsWith(' ') -or $Value.EndsWith('.')) {
        throw "$Description ist ungueltig."
    }
    $deviceName = $Value.Split('.')[0]
    if ($deviceName -match '\A(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])\z') {
        throw "$Description ist unter Windows unzulaessig."
    }
}

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
    if (($spec -isnot [pscustomobject]) -or ($spec.format_version -ne 1) -or
        ($spec.runtime -isnot [pscustomobject])) {
        throw 'Der Python-Datensatz hat ein ungueltiges Format.'
    }
    $runtimeVersion = $spec.runtime.version
    $directoryName = $spec.runtime.directory_name
    $executableName = $spec.runtime.executable
    if (($runtimeVersion -isnot [string]) -or
        ($runtimeVersion -cnotmatch '\A[0-9]+\.[0-9]+\.[0-9]+\z')) {
        throw 'Die Python-Version ist ungueltig.'
    }
    Test-SingleWindowsName -Value $directoryName -Description 'Der Laufzeitordnername'
    Test-SingleWindowsName -Value $executableName -Description 'Der Python-Dateiname'

    $runtimeRoot = Get-Item -LiteralPath $RuntimeRootPath -Force
    if (($runtimeRoot -isnot [System.IO.DirectoryInfo]) -or
        (($runtimeRoot.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw 'Der Laufzeit-Stammordner muss ein lokaler, direkter Ordner sein.'
    }
    $rootFullPath = $runtimeRoot.FullName.TrimEnd([System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar)
    $staging = Get-Item -LiteralPath $StagingPath -Force
    if (($staging -isnot [System.IO.DirectoryInfo]) -or
        (($staging.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw 'Der temporaere Laufzeitordner muss ein lokaler, direkter Ordner sein.'
    }
    if (-not [System.IO.Path]::GetDirectoryName($staging.FullName).Equals(
        $rootFullPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Der temporaere Laufzeitordner muss direkt im Laufzeit-Stammordner liegen.'
    }
    $stagedExecutable = Get-Item -LiteralPath (Join-Path $staging.FullName $executableName) -Force
    if (($stagedExecutable -isnot [System.IO.FileInfo]) -or
        (($stagedExecutable.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw 'Die entpackte Python-Programmdatei fehlt oder ist unzulaessig.'
    }

    $targetPath = Join-Path $rootFullPath $directoryName
    $markerName = '.ak-weather-runtime.json'
    $markerPath = Join-Path $targetPath $markerName
    if (Test-Path -LiteralPath $targetPath) {
        $target = Get-Item -LiteralPath $targetPath -Force
        $targetExecutablePath = Join-Path $targetPath $executableName
        if (($target -isnot [System.IO.DirectoryInfo]) -or
            (($target.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw 'Der vorhandene Laufzeitordner ist nicht eindeutig passend.'
        }
        $targetExecutable = Get-Item -LiteralPath $targetExecutablePath -Force
        $markerFile = Get-Item -LiteralPath $markerPath -Force
        if (($targetExecutable -isnot [System.IO.FileInfo]) -or
            (($targetExecutable.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) -or
            ($markerFile -isnot [System.IO.FileInfo]) -or
            (($markerFile.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw 'Der vorhandene Laufzeitordner ist nicht eindeutig passend.'
        }
        $marker = ConvertFrom-Json -InputObject ([System.IO.File]::ReadAllText($markerPath))
        if (($marker.format_version -ne 1) -or ($marker.runtime_version -cne $runtimeVersion) -or
            ($marker.directory_name -cne $directoryName) -or
            ($marker.executable -cne $executableName)) {
            throw 'Der vorhandene Laufzeitordner gehoert zu einer anderen Laufzeit.'
        }
        Write-Output 'Vorhandene passende Python-Laufzeit wird unveraendert wiederverwendet.'
    } else {
        $stagingMarker = Join-Path $staging.FullName $markerName
        if (Test-Path -LiteralPath $stagingMarker) {
            throw 'Der temporaere Laufzeitordner enthaelt bereits eine Markierungsdatei.'
        }
        $marker = [ordered]@{
            format_version = 1
            runtime_version = $runtimeVersion
            directory_name = $directoryName
            executable = $executableName
        } | ConvertTo-Json
        [System.IO.File]::WriteAllText($stagingMarker, $marker + [Environment]::NewLine,
            [System.Text.UTF8Encoding]::new($false))
        [System.IO.Directory]::Move($staging.FullName, $targetPath)
        Write-Output 'Python-Laufzeit atomar unter dem versionsgebundenen Namen bereitgestellt.'
    }
} catch {
    [Console]::Error.WriteLine('Fehler beim Veroeffentlichen der Python-Laufzeit: ' + $_.Exception.Message)
    $result = 1
}
exit $result
