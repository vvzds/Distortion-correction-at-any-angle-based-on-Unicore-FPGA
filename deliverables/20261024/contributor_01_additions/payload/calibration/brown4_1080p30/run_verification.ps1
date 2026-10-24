param(
    [string]$Python = '',
    [string]$IverilogRoot = '',
    [string[]]$Cases = @('source_words','uart','boundary','map','bilinear','cache','identity','real_highfreq'),
    [switch]$SkipVectorGeneration
)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
if (!$Python) {
    $foundPython=Get-Command python.exe -ErrorAction SilentlyContinue
    if ($foundPython) { $Python=$foundPython.Source }
    else { $Python=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' }
}
if (!$IverilogRoot) { $IverilogRoot=[IO.Path]::GetFullPath((Join-Path $root '..\..\work\simulator\iverilog\app')) }
$drive=$null
foreach($candidate in @('Z','Y','X','W','V','U')) {
    if (!(Test-Path "${candidate}:\")) { $drive=$candidate;break }
}
if(!$drive){throw 'No free temporary tool drive.'}
& subst "${drive}:" $IverilogRoot
if($LASTEXITCODE -ne 0){throw 'Could not create temporary Icarus tool drive.'}
$iv="${drive}:\bin\iverilog.exe"
$vvp="${drive}:\bin\vvp.exe"
$rtl='received/G4/source/rtl/'
$fullCore=@(($rtl+'undistort_core.v'),($rtl+'undistort_map.v'),($rtl+'undistort_line_cache.v'),($rtl+'undistort_bilinear.v'))
$suite=@{
    source_words=@('calibration_source_words_tb',@('sim/calibration_source_words_tb.v'),@(),'SOURCE_WORDS PASS pixels=4147200','2012')
    uart=@('calibration_uart_tb',@('sim/calibration_uart_tb.v','received/integration/integ_ws_regression_pkg_20261019/source/rtl/param_mgr.v'),@(),'UART PASS','2012')
    boundary=@('calibration_boundary_tb',@('sim/calibration_boundary_tb.v',($rtl+'undistort_map.v')),@(),'BOUNDARY PASS','2012')
    map=@('calibration_map_tb',@('sim/calibration_map_tb.v',($rtl+'undistort_map.v')),@(),'MAP PASS pixels=2073600','2012')
    bilinear=@('undistort_bilinear_tb',@('received/G4/sim/undistort_bilinear_tb.v',($rtl+'undistort_bilinear.v')),@(),'=== ALL TESTS PASSED (err=0) ===','2001')
    cache=@('undistort_line_cache_tb',@('received/G4/sim/undistort_line_cache_tb.v',($rtl+'undistort_line_cache.v')),@(),'=== ALL TESTS PASSED (err=0) ===','2001')
    identity=@('calibration_core_tb',(@('sim/calibration_core_tb.v')+$fullCore),@('+MODE=0','+PATTERN=1','+SLOT=0','+VECTOR=vectors/identity_pixels.hex'),'CORE PASS mode=0','2012')
    real_highfreq=@('calibration_core_tb',(@('sim/calibration_core_tb.v')+$fullCore),@('+MODE=1','+PATTERN=1','+SLOT=3','+VECTOR=vectors/real_pixels_1.hex'),'CORE PASS mode=1 pattern=1','2012')
    real_smooth=@('calibration_core_tb',(@('sim/calibration_core_tb.v')+$fullCore),@('+MODE=1','+PATTERN=0','+SLOT=2','+VECTOR=vectors/real_pixels_0.hex'),'CORE PASS mode=1 pattern=0','2012')
}
Push-Location $root
try {
    if(!$SkipVectorGeneration) {
        & $Python prepare_and_check.py 2>&1 | Tee-Object -FilePath logs/vector_generation.log
        if($LASTEXITCODE -ne 0){throw 'Vector generation or independent floating reference failed.'}
    }
    foreach($caseName in $Cases){
        if(!$suite.ContainsKey($caseName)){throw "Unknown case: $caseName"}
        $config=$suite[$caseName]
        $top=$config[0];$sources=$config[1];$simArgs=$config[2];$pass=$config[3];$language=$config[4]
        $logName=switch($caseName){'map'{'map_full'} 'identity'{'core_identity'} 'real_highfreq'{'core_real_highfreq'} default{$caseName}}
        & $iv -B "${drive}:\lib\ivl" "-g$language" -I . -s $top -o "sim/$caseName.vvp" @sources 2>&1 | Tee-Object -FilePath "logs/$caseName.compile.log"
        if($LASTEXITCODE -ne 0){throw "Compile failed: $caseName"}
        $timer=[Diagnostics.Stopwatch]::StartNew()
        & $vvp -i "sim/$caseName.vvp" @simArgs 2>&1 | Tee-Object -FilePath "logs/$logName.log"
        $code=$LASTEXITCODE;$timer.Stop()
        $text=Get-Content -LiteralPath "logs/$logName.log" -Raw
        $ok=$code -eq 0 -and $text.Contains($pass) -and $text -notmatch 'FATAL|FAIL|TIMEOUT|MISMATCH|ERROR:'
        @{case=$caseName;exit_code=$code;pass=$ok;elapsed_seconds=$timer.Elapsed.TotalSeconds} |
            ConvertTo-Json | Set-Content -LiteralPath "reports/$caseName.result.json" -Encoding utf8
        if(!$ok){throw "Simulation failed: $caseName"}
    }
} finally { Pop-Location; & subst "${drive}:" /D }
