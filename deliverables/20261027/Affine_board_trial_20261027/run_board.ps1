[CmdletBinding()]
param(
    [ValidateSet('selftest','list','init','status','demo','reset','preview','track')]
    [string]$Mode = 'selftest',
    [string]$Port = '',
    [int]$Camera = 0,
    [string]$PythonExe = '',
    [double]$Settle = 0.15,
    [double]$Gain = 0.6,
    [double]$Scale = 0.25,
    [double]$MaxRotStep = 1.25,
    [double]$MaxShiftStep = 40,
    [double]$AbsoluteRotLimit = 20,
    [double]$AbsoluteShiftLimit = 800,
    [int]$LowConfidenceFrames = 3,
    [double]$RecoverConfidence = 0.75,
    [int]$RecoverFrames = 2
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
if (-not $PythonExe) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) { $PythonExe = $pythonCommand.Source }
    else { throw 'Python 3.10+ required. Set -PythonExe to the full path of python.exe.' }
}
& $PythonExe -c 'import sys, cv2, numpy, serial; assert sys.version_info >= (3,10), "Python 3.10+ required"'
if ($LASTEXITCODE -ne 0) {
    Write-Host ('Install dependencies: & "{0}" -m pip install -r "{1}"' -f $PythonExe, (Join-Path $PSScriptRoot '02_host\requirements.txt'))
    exit 1
}
$culture = [System.Globalization.CultureInfo]::InvariantCulture
$scriptArgs = @((Join-Path $PSScriptRoot '02_host\board_trial.py'), $Mode,
    '--cam', $Camera.ToString($culture), '--settle', $Settle.ToString($culture),
    '--gain', $Gain.ToString($culture), '--scale', $Scale.ToString($culture),
    '--max-rot-step', $MaxRotStep.ToString($culture),
    '--max-shift-step', $MaxShiftStep.ToString($culture),
    '--absolute-rot-limit', $AbsoluteRotLimit.ToString($culture),
    '--absolute-shift-limit', $AbsoluteShiftLimit.ToString($culture),
    '--low-confidence-frames', $LowConfidenceFrames.ToString($culture),
    '--recover-confidence', $RecoverConfidence.ToString($culture),
    '--recover-frames', $RecoverFrames.ToString($culture))
if ($Port) { $scriptArgs += @('--port', $Port) }
& $PythonExe @scriptArgs
exit $LASTEXITCODE
