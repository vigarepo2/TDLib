$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "../scripts/Invoke-Checked.ps1")
$Expected = @("-S", "path with spaces", "-B", "other path", "--build", "-DCMAKE_INSTALL_PREFIX=C:/path with spaces")
$Actual = Invoke-Checked -Program python -Arguments (@("-c", "import json,sys; print(json.dumps(sys.argv[1:]))") + $Expected)
$Decoded = $Actual | ConvertFrom-Json
if (Compare-Object $Expected $Decoded -SyncWindow 0) { throw "Native argument forwarding changed a switch or path" }
$Failed = $false
try {
    Invoke-Checked -Program python -Arguments @("-c", "import sys; sys.exit(7)")
} catch {
    if ($_.Exception.Message -notmatch 'exit 7') { throw }
    $Failed = $true
}
if (-not $Failed) { throw "A failing native command was incorrectly accepted" }
# Clear the deliberately failed native status for callers which inspect it.
Invoke-Checked -Program python -Arguments @("-c", "pass")
Write-Host "PowerShell native switch/path forwarding and nonzero-exit checks passed"
