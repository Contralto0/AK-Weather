[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$StagingPath,
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$LibraryRootPath,
    [string]$MetadataPath
)

# Windows PowerShell 5.1; veröffentlicht nur einen bereits geprüften GUI-Stagingordner.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$result = 0

function Test-SingleWindowsName {
    param([object]$Value, [string]$Description)
    if (($Value -isnot [string]) -or [string]::IsNullOrWhiteSpace($Value) -or
        ($Value -ne [System.IO.Path]::GetFileName($Value)) -or $Value.Contains(':') -or
        $Value.EndsWith(' ') -or $Value.EndsWith('.')) {
        throw "$Description ist ungültig."
    }
    if ($Value.Split('.')[0] -match '\A(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])\z') {
        throw "$Description ist unter Windows unzulässig."
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
        ($spec.target -isnot [pscustomobject]) -or ($spec.deployment -isnot [pscustomobject])) {
        throw 'Der GUI-Datensatz hat ein ungültiges Format.'
    }
    $versions = @($spec.packages | ForEach-Object { $_.version } | Select-Object -Unique)
    if (($versions.Count -ne 1) -or ($versions[0] -isnot [string]) -or
        ($versions[0] -cnotmatch '\A[0-9]+\.[0-9]+\.[0-9]+\z')) {
        throw 'Die GUI-Paketversion ist ungültig oder nicht eindeutig.'
    }
    $guiVersion = $versions[0]
    $pythonVersion = $spec.target.python_version
    if (($pythonVersion -isnot [string]) -or
        ($pythonVersion -cnotmatch '\A[0-9]+\.[0-9]+\.[0-9]+\z')) {
        throw 'Die Python-Zielversion ist ungültig.'
    }
    $directoryName = $spec.deployment.directory_name
    $markerName = $spec.deployment.marker_name
    Test-SingleWindowsName $directoryName 'Der Bibliothekspaket-Ordnername'
    Test-SingleWindowsName $markerName 'Der Markierungsdateiname'
    $requiredDirectories = @($spec.deployment.required_directories)
    if ($requiredDirectories.Count -ne 2) { throw 'Die erforderlichen GUI-Ordner sind ungültig.' }
    foreach ($requiredDirectory in $requiredDirectories) {
        Test-SingleWindowsName $requiredDirectory 'Ein erforderlicher GUI-Ordnername'
    }

    $libraryRoot = Get-Item -LiteralPath $LibraryRootPath -Force
    if (($libraryRoot -isnot [System.IO.DirectoryInfo]) -or
        (($libraryRoot.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw 'Der Bibliotheks-Stammordner muss ein lokaler, direkter Ordner sein.'
    }
    $rootFullPath = $libraryRoot.FullName.TrimEnd('\', '/')
    $staging = Get-Item -LiteralPath $StagingPath -Force
    if (($staging -isnot [System.IO.DirectoryInfo]) -or
        (($staging.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) -or
        (-not [System.IO.Path]::GetDirectoryName($staging.FullName).Equals(
            $rootFullPath, [System.StringComparison]::OrdinalIgnoreCase))) {
        throw 'Der GUI-Stagingordner muss direkt im Bibliotheks-Stammordner liegen.'
    }
    foreach ($requiredDirectory in $requiredDirectories) {
        $required = Get-Item -LiteralPath (Join-Path $staging.FullName $requiredDirectory) -Force
        if (($required -isnot [System.IO.DirectoryInfo]) -or
            (($required.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw "Der erforderliche GUI-Ordner fehlt oder ist unzulässig: $requiredDirectory"
        }
    }

    $targetPath = Join-Path $rootFullPath $directoryName
    $markerPath = Join-Path $targetPath $markerName
    if (Test-Path -LiteralPath $targetPath) {
        $target = Get-Item -LiteralPath $targetPath -Force
        $markerFile = Get-Item -LiteralPath $markerPath -Force
        if (($target -isnot [System.IO.DirectoryInfo]) -or
            (($target.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) -or
            ($markerFile -isnot [System.IO.FileInfo]) -or
            (($markerFile.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw 'Das vorhandene GUI-Bibliothekspaket ist nicht eindeutig passend.'
        }
        $marker = ConvertFrom-Json -InputObject ([System.IO.File]::ReadAllText($markerPath))
        if (($marker.format_version -ne 1) -or ($marker.gui_version -cne $guiVersion) -or
            ($marker.python_version -cne $pythonVersion) -or
            ($marker.directory_name -cne $directoryName)) {
            throw 'Das vorhandene GUI-Bibliothekspaket gehört zu einer anderen Version.'
        }
        foreach ($requiredDirectory in $requiredDirectories) {
            if (-not [System.IO.Directory]::Exists((Join-Path $targetPath $requiredDirectory))) {
                throw 'Das vorhandene GUI-Bibliothekspaket ist unvollständig.'
            }
        }
        Write-Output 'Vorhandenes passendes GUI-Bibliothekspaket wird unverändert wiederverwendet.'
    } else {
        $stagingMarker = Join-Path $staging.FullName $markerName
        if (Test-Path -LiteralPath $stagingMarker) {
            throw 'Der GUI-Stagingordner enthält bereits eine Markierungsdatei.'
        }
        $marker = [ordered]@{
            format_version = 1
            gui_version = $guiVersion
            python_version = $pythonVersion
            directory_name = $directoryName
        } | ConvertTo-Json
        [System.IO.File]::WriteAllText($stagingMarker, $marker + [Environment]::NewLine,
            [System.Text.UTF8Encoding]::new($false))
        [System.IO.Directory]::Move($staging.FullName, $targetPath)
        Write-Output 'GUI-Bibliothekspaket atomar unter dem versionsgebundenen Namen bereitgestellt.'
    }
} catch {
    [Console]::Error.WriteLine('Fehler beim Veröffentlichen des GUI-Bibliothekspakets: ' +
        $_.Exception.Message)
    $result = 1
}
exit $result
