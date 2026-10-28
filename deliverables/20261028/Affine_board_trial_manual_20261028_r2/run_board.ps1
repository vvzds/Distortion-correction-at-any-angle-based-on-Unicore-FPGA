[CmdletBinding()]
param(
    [ValidateSet('selftest','list','init','status','demo','reset','preview','track')]
    [string]$Mode = 'selftest',
    [string]$Port = '',
    [int]$Camera = 0,
    [string]$PythonExe = '',
    [double]$Settle = 0.15,
    [double]$Gain = 0.9,
    [double]$Scale = 0.25,
    [double]$MaxRotStep = 6,
    [double]$MaxShiftStep = 100,
    [double]$AbsoluteRotLimit = 40,
    [double]$AbsoluteShiftLimit = 1500,
    [double]$EstimateBudget = 0.3,
    [double]$MaxFrameAge = 0.6,
    [double]$MaxCornerStep = 180,
    [double]$EccMin = 0.65,
    [double]$DeadbandPx = 1.2,
    [ValidateSet('affine','similarity')][string]$Model = 'affine',
    [ValidateSet('checked','features')][string]$Refine = 'checked',
    [double]$AutoSnapshot = 5,
    [switch]$NoVideo
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
    '--estimate-budget', $EstimateBudget.ToString($culture),
    '--max-frame-age', $MaxFrameAge.ToString($culture),
    '--max-corner-step', $MaxCornerStep.ToString($culture),
    '--ecc-min', $EccMin.ToString($culture), '--deadband-px', $DeadbandPx.ToString($culture),
    '--model', $Model, '--refine', $Refine, '--auto-snapshot', $AutoSnapshot.ToString($culture))
if ($NoVideo) { $scriptArgs += '--no-video' }
if ($Port) { $scriptArgs += @('--port', $Port) }
& $PythonExe @scriptArgs
exit $LASTEXITCODE
