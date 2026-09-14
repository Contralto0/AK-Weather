[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$RuntimeRootPath,
    [string]$MetadataPath,
    [scriptblock]$DownloadAction
)

# Windows PowerShell 5.1; verbindet vorhandene Bootstrap-Bausteine, startet Python nicht.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$stagingPath = $null
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

function Test-ExistingRuntime {
    param([string]$TargetPath, [pscustomobject]$Runtime)
    if (-not (Test-Path -LiteralPath $TargetPath)) { return $false }
    $target = Get-Item -LiteralPath $TargetPath -Force
    $executable = Get-Item -LiteralPath (Join-Path $TargetPath $Runtime.executable) -Force
    $markerFile = Get-Item -LiteralPath (Join-Path $TargetPath '.ak-weather-runtime.json') -Force
    if (($target -isnot [System.IO.DirectoryInfo]) -or
        (($target.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) -or
        ($executable -isnot [System.IO.FileInfo]) -or
        (($executable.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) -or
        ($markerFile -isnot [System.IO.FileInfo]) -or
        (($markerFile.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw 'Der vorhandene Laufzeitordner ist nicht eindeutig passend.'
    }
    $marker = ConvertFrom-Json -InputObject ([System.IO.File]::ReadAllText($markerFile.FullName))
    if (($marker.format_version -ne 1) -or
        ($marker.runtime_version -cne $Runtime.version) -or
        ($marker.directory_name -cne $Runtime.directory_name) -or
        ($marker.executable -cne $Runtime.executable)) {
        throw 'Der vorhandene Laufzeitordner gehoert zu einer anderen Laufzeit.'
    }
    return $true
}

function Invoke-BootstrapStep {
    param([string]$ScriptPath, [string[]]$Arguments, [string]$Description)
    $powerShell = Join-Path $PSHOME 'powershell.exe'
    & $powerShell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned `
        -File $ScriptPath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Description ist fehlgeschlagen." }
}

try {
    $scriptDirectory = [System.IO.Path]::GetDirectoryName($MyInvocation.MyCommand.Path)
    if (-not $PSBoundParameters.ContainsKey('MetadataPath')) {
        $MetadataPath = Join-Path $scriptDirectory 'windows-python.lock.json'
    }
    $metadataFile = Get-Item -LiteralPath $MetadataPath -Force
    if ($metadataFile -isnot [System.IO.FileInfo]) {
        throw 'Der Python-Datensatz muss eine lokale Datei sein.'
    }
    $spec = ConvertFrom-Json -InputObject ([System.IO.File]::ReadAllText($metadataFile.FullName))
    if (($spec -isnot [pscustomobject]) -or ($spec.format_version -ne 1) -or
        ($spec.runtime -isnot [pscustomobject]) -or ($spec.archive -isnot [pscustomobject])) {
        throw 'Der Python-Datensatz hat ein ungueltiges Format.'
    }
    if (($spec.runtime.version -isnot [string]) -or
        ($spec.runtime.version -cnotmatch '\A[0-9]+\.[0-9]+\.[0-9]+\z')) {
        throw 'Die Python-Version ist ungueltig.'
    }
    Test-SingleWindowsName -Value $spec.runtime.directory_name -Description 'Der Laufzeitordnername'
    Test-SingleWindowsName -Value $spec.runtime.executable -Description 'Der Python-Dateiname'
    Test-SingleWindowsName -Value $spec.archive.filename -Description 'Der Archivdateiname'
    $runtimeRoot = Get-Item -LiteralPath $RuntimeRootPath -Force
    if (($runtimeRoot -isnot [System.IO.DirectoryInfo]) -or
        (($runtimeRoot.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw 'Der Laufzeit-Stammordner muss ein lokaler, direkter Ordner sein.'
    }
    $targetPath = Join-Path $runtimeRoot.FullName $spec.runtime.directory_name
    if (Test-ExistingRuntime -TargetPath $targetPath -Runtime $spec.runtime) {
        Write-Output 'Vorhandene passende Python-Laufzeit ohne Download wiederverwendet.'
    } else {
        $archivePath = Join-Path $runtimeRoot.FullName $spec.archive.filename
        if ($PSBoundParameters.ContainsKey('DownloadAction') -and
            -not [System.IO.File]::Exists($archivePath)) {
            $null = & $DownloadAction ([System.Uri]$spec.archive.url) $archivePath
        }
        Invoke-BootstrapStep -ScriptPath (Join-Path $scriptDirectory 'Get-PythonArchive.ps1') `
            -Arguments @('-DestinationPath', $archivePath, '-MetadataPath', $metadataFile.FullName) `
            -Description 'Download und Archivpruefung'

        $stagingPath = Join-Path $runtimeRoot.FullName ('.' + $spec.runtime.directory_name + '.' +
            [System.Guid]::NewGuid().ToString('N') + '.staging')
        Invoke-BootstrapStep -ScriptPath (Join-Path $scriptDirectory 'Expand-PythonArchive.ps1') `
            -Arguments @('-ArchivePath', $archivePath, '-DestinationPath', $stagingPath) `
            -Description 'Sicheres Entpacken'
        Invoke-BootstrapStep -ScriptPath (Join-Path $scriptDirectory 'Publish-PythonRuntime.ps1') `
            -Arguments @('-StagingPath', $stagingPath, '-RuntimeRootPath', $runtimeRoot.FullName,
                '-MetadataPath', $metadataFile.FullName) -Description 'Atomare Veroeffentlichung'
        $stagingPath = $null
        Write-Output 'Portable Python-Laufzeit vollstaendig bereitgestellt.'
    }
} catch {
    [Console]::Error.WriteLine('Fehler beim Einrichten der Python-Laufzeit: ' + $_.Exception.Message)
    $result = 1
} finally {
    if (($null -ne $stagingPath) -and [System.IO.Directory]::Exists($stagingPath)) {
        [System.IO.Directory]::Delete($stagingPath, $true)
    }
}
exit $result
