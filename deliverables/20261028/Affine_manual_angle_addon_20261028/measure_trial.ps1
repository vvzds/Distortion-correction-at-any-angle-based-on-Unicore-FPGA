[CmdletBinding()]
param(
    [string]$Session = '',
    [string]$PythonExe = '',
    [string]$Points = '',
    [string]$Out = '',
    [ValidateRange(4,8)][int]$Count = 4,
    [double]$ClickError = 2.0
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
if (-not $PythonExe) { $PythonExe = (Get-Command python -ErrorAction Stop).Source }
& $PythonExe -c 'import cv2, numpy, tkinter'
if ($LASTEXITCODE -ne 0) { throw 'Use the Python environment installed for the board-trial package (GUI OpenCV and tkinter required).' }
$culture = [System.Globalization.CultureInfo]::InvariantCulture
$scriptArgs = @((Join-Path $PSScriptRoot 'angle_measure.py'), '--count', $Count.ToString($culture),
    '--click-error', $ClickError.ToString($culture))
if ($Session) { $scriptArgs += @('--session', $Session) }
if ($Points) { $scriptArgs += @('--points', $Points) }
if ($Out) { $scriptArgs += @('--out', $Out) }
& $PythonExe @scriptArgs
exit $LASTEXITCODE
