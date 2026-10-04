# Keep native switches inside an explicit array: PowerShell must not bind -S,
# -B or other tool arguments as parameters of this wrapper function.
function Invoke-Checked {
    param([Parameter(Mandatory = $true)][string]$Program,
          [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed (exit $LASTEXITCODE)" }
}
