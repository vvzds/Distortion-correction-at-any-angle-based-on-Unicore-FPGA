param(
    [string]$PdsRoot = 'D:\FPGA PDS\PDS_2022.2-SP6.1-win64'
)
$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$pdsShell = Join-Path $PdsRoot 'bin\pds_shell.exe'
if (-not (Test-Path -LiteralPath $pdsShell)) { throw "PDS not found: $pdsShell" }

# PDS 2022.2's bundled Tcl may normalize Windows known folders incorrectly.
# A temporary drive gives it a short ASCII path while keeping files in place.
$driveLetter = $null
foreach ($candidate in @('Q','R','S','T','U','V','W','X','Y','Z')) {
    if (-not (Test-Path "${candidate}:\")) { $driveLetter = $candidate; break }
}
if (-not $driveLetter) { throw 'No free drive letter for the temporary project mapping.' }
& subst "${driveLetter}:" $projectDirectory
if ($LASTEXITCODE -ne 0) { throw 'Could not create the temporary project mapping.' }
try {
    $mappedRoot = "${driveLetter}:/"
    $buildStartedUtc = [DateTime]::UtcNow
    $logFile = Join-Path $projectDirectory 'build_console.log'
    & $pdsShell -file "${mappedRoot}build.tcl" -work_dir $mappedRoot -project_name task1_1080p30 2>&1 |
        Tee-Object -FilePath $logFile
    if ($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $logFile -Pattern '^E:' -Quiet)) {
        throw 'PDS build failed. Read build_console.log; do not use an older bitstream.'
    }
    $bitstream = Join-Path $projectDirectory 'generate_bitstream\hdmi_ddr_ov5640_top.sbit'
    if (-not (Test-Path -LiteralPath $bitstream)) { throw 'PDS did not generate the bitstream.' }
    if ((Get-Item -LiteralPath $bitstream).LastWriteTimeUtc -lt $buildStartedUtc) {
        throw 'Bitstream was not updated by this build; do not download the older file.'
    }
    Write-Host "Build finished: $bitstream"
} finally {
    & subst "${driveLetter}:" /D
}
