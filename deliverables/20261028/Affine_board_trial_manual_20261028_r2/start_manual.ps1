[CmdletBinding()]
param([string]$PythonExe = '')
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath $PSScriptRoot
if (-not $PythonExe) { $PythonExe = (Get-Command python -ErrorAction Stop).Source }
Write-Host '人工动态仿射板测 manual-20261028-r2'
Write-Host '先阅读 README_板测.md。初始化、原图和日志会自动记录。'
Write-Host '遇到跑偏：先点击预览窗口，再按 D；Q 为正常退出。'
$portInput = Read-Host '输入串口名，直接回车使用 COM11'
if (-not $portInput) { $portInput = 'COM11' }
$cameraInput = Read-Host '输入HDMI采集卡编号，直接回车使用 0'
if (-not $cameraInput) { $cameraInput = '0' }
$cameraNumber = 0
if (-not [int]::TryParse($cameraInput, [ref]$cameraNumber) -or $cameraNumber -lt 0) {
    throw '采集卡编号需要是0或更大的整数。'
}
while ($true) {
    Write-Host ''
    Write-Host '1 查看串口列表'
    Write-Host '2 检查采集画面（不发串口指令）'
    Write-Host '3 固定指令演示（自动初始化并记录各阶段截图）'
    Write-Host '4 动态跟踪：推荐快档（首次先小幅转动）'
    Write-Host '5 动态跟踪：较稳档（若快档振荡再试）'
    Write-Host '6 关闭仿射（不重新标定，不改变已加载畸变参数）'
    Write-Host '7 打包全部会话用于回传'
    Write-Host '8 运行软件自检（不连接板卡）'
    Write-Host '0 退出菜单'
    $choice = Read-Host '输入数字后回车'
    if ($choice -eq '0') { break }
    if ($choice -eq '7') {
        & $PythonExe (Join-Path $PSScriptRoot '02_host\export_results.py')
    }
    else {
        $mode = switch ($choice) {
            '1' { 'list' }; '2' { 'preview' }; '3' { 'demo' }; '4' { 'track' }
            '5' { 'track' }; '6' { 'reset' }; '8' { 'selftest' }; default { '' }
        }
        if (-not $mode) { Write-Host '请输入菜单中的数字。'; continue }
        $runArgs = @{ Mode=$mode; Port=$portInput; Camera=$cameraNumber; PythonExe=$PythonExe }
        if ($choice -eq '5') { $runArgs.Settle=.25; $runArgs.Gain=.6; $runArgs.MaxRotStep=3; $runArgs.MaxShiftStep=60; $runArgs.MaxCornerStep=100 }
        & (Join-Path $PSScriptRoot 'run_board.ps1') @runArgs
    }
    if ($LASTEXITCODE -ne 0) { Write-Host '本次操作返回错误，请保留提示；记录仍在sessions中。' }
}
