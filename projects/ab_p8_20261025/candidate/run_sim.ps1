param([string[]]$Cases=@('cache72'),[string]$Out='', [string]$Python='python',
      [string]$IverilogRoot='', [int]$Jobs=1)
$ErrorActionPreference='Stop'
if (!$Out) { throw 'Specify a NEW evidence directory using -Out' }
$runArgs=@('-B','-X','utf8',(Join-Path $PSScriptRoot 'run_validation.py'),
           '--out',$Out,'--jobs',"$Jobs",'--cases')+$Cases
if($IverilogRoot){$runArgs+=@('--tool-root',$IverilogRoot)}
& $Python @runArgs
exit $LASTEXITCODE
