$ErrorActionPreference = 'Stop'
$taskRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$planPath = Join-Path $taskRoot 'plan.json'
$plan = Get-Content -LiteralPath $planPath -Raw -Encoding utf8 | ConvertFrom-Json
$recovery = Get-Content -LiteralPath (Join-Path $taskRoot 'recovery_verification.json') -Raw -Encoding utf8 | ConvertFrom-Json
if ($recovery.status -ne 'PASS' -or (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $recovery.plan_sha256) { throw 'Recovery verification missing or plan changed' }
$allowedBases = @(
    'C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work',
    'C:\Users\叶翔\Desktop\yx\本机项目全量归档上传_二号_20261024',
    'D:\FPGA PDS\yx'
)
$allowedExternal = @(
    'C:\Users\叶翔\Desktop\yx\本机项目全量归档上传_二号_20261024\完整归档',
    'D:\FPGA PDS\yx\static_G4_bringup_20261024',
    'D:\FPGA PDS\yx\static_G4_timing_resume_20261024'
)
$targetSet = @{}
foreach ($t in $plan.targets) {
    $resolvedTarget = [System.IO.Path]::GetFullPath($t).TrimEnd('\')
    $contained = $false
    foreach ($b in $allowedBases) { if ($resolvedTarget.StartsWith($b + '\',[System.StringComparison]::OrdinalIgnoreCase)) { $contained = $true } }
    if (-not $contained) { throw "Out-of-scope target: $resolvedTarget" }
    if (-not $resolvedTarget.StartsWith($allowedBases[0] + '\',[System.StringComparison]::OrdinalIgnoreCase) -and $resolvedTarget -notin $allowedExternal) { throw "Unlisted external target: $resolvedTarget" }
    $targetSet[$resolvedTarget] = $true
}
# Validate all resolved file boundaries before deleting anything. Never follow reparse points.
foreach ($f in $plan.files) {
    $target = [System.IO.Path]::GetFullPath($f.target).TrimEnd('\')
    $full = [System.IO.Path]::GetFullPath($f.path)
    if (-not $targetSet.ContainsKey($target)) { throw 'Unknown target' }
    if ($full -ne $target -and -not $full.StartsWith($target + '\',[System.StringComparison]::OrdinalIgnoreCase)) { throw "Escaped target: $full" }
    $item = Get-Item -LiteralPath $full -Force
    if ($item.PSIsContainer -or ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) { throw "Not a plain file: $full" }
    $ancestor = $item.Directory
    while ($null -ne $ancestor) {
        if ($ancestor.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw "Reparse ancestor: $($ancestor.FullName)" }
        $ancestor = $ancestor.Parent
    }
}
$journalPath = Join-Path $taskRoot 'deletion_journal.jsonl'
if (Test-Path -LiteralPath $journalPath) { throw 'Journal already exists; do not rerun blindly' }
$journal = [System.IO.StreamWriter]::new($journalPath,$false,[System.Text.UTF8Encoding]::new($false))
$journal.AutoFlush = $true
$deletedCount=0; $deletedBytes=[long]0; $failureCount=0
$before = @(Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Name -in @('C','D')} | Select-Object Name,Free)
try {
    foreach ($f in $plan.files) {
        $result = [ordered]@{path=$f.path; bytes=$f.bytes; sha256=$f.sha256; status='SKIPPED'; time=(Get-Date).ToString('o')}
        try {
            $item = Get-Item -LiteralPath $f.path -Force
            if ($item.Length -ne $f.bytes) { throw 'Size changed since verification' }
            if ((Get-FileHash -LiteralPath $f.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { throw 'Hash changed since verification' }
            if ($f.keep_path) {
                if ((Get-FileHash -LiteralPath $f.keep_path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $f.sha256) { throw 'Retained duplicate changed' }
            }
            Remove-Item -LiteralPath $f.path -Force -ErrorAction Stop
            $result.status='DELETED'; $deletedCount++; $deletedBytes += [long]$f.bytes
        } catch { $result.error=$_.Exception.Message; $failureCount++ }
        $journal.WriteLine(($result | ConvertTo-Json -Compress))
        if (($deletedCount + $failureCount) % 2000 -eq 0) { Write-Output "Processed $($deletedCount + $failureCount), deleted $deletedCount, bytes $deletedBytes" }
    }
} finally { $journal.Dispose() }
# Remove only empty ancestor directories of deleted files, with no recursive deletion.
$dirs = @{}
foreach ($f in $plan.files) {
    $target=[System.IO.Path]::GetFullPath($f.target).TrimEnd('\')
    $parent=[System.IO.Path]::GetDirectoryName($f.path)
    while ($parent -and ($parent -eq $target -or $parent.StartsWith($target+'\',[System.StringComparison]::OrdinalIgnoreCase))) {
        $dirs[$parent]=$true
        if ($parent -eq $target) { break }
        $parent=[System.IO.Path]::GetDirectoryName($parent)
    }
}
foreach ($dir in ($dirs.Keys | Sort-Object Length -Descending)) {
    if ([System.IO.Directory]::Exists($dir)) {
        try { [System.IO.Directory]::Delete($dir,$false) } catch { }
    }
}
$after = @(Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Name -in @('C','D')} | Select-Object Name,Free)
$summary=[ordered]@{completed=(Get-Date).ToString('o');deleted_files=$deletedCount;deleted_logical_bytes=$deletedBytes;skipped_or_failed_files=$failureCount;before=$before;after=$after;plan_sha256=$recovery.plan_sha256}
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $taskRoot 'cleanup_result.json') -Encoding utf8
$summary | ConvertTo-Json -Depth 6
