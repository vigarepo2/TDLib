# Build the official TDLib JSON ABI for 64-bit Windows. Run with PowerShell 7.
[CmdletBinding()]
param(
    [string]$Source = "upstream",
    [string]$Output = "dist/windows-x64",
    [string]$WorkDir = ".native-build/windows",
    [ValidateRange(1, 4)][int]$Parallel = 2
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$Root = Split-Path -Parent $PSScriptRoot
$Config = Get-Content (Join-Path $Root "config/build.json") -Raw | ConvertFrom-Json
function Invoke-Checked {
    param([string]$Program, [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed (exit $LASTEXITCODE)" }
}
if (-not $IsWindows -or -not [Environment]::Is64BitOperatingSystem) {
    throw "This recipe requires a 64-bit Windows host and Visual Studio 2022 C++ tools."
}
foreach ($Command in @("git", "cmake", "python")) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) { throw "Missing command: $Command" }
}
$Source = (Resolve-Path $Source).Path
$Commit = (& git -C $Source rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $Commit -notmatch '^[a-f0-9]{40}$') { throw "Invalid source checkout" }
Invoke-Checked git -C $Source diff --quiet
Invoke-Checked git -C $Source diff --cached --quiet
New-Item -ItemType Directory -Force -Path $WorkDir, $Output | Out-Null
$WorkDir = (Resolve-Path $WorkDir).Path
$Output = (Resolve-Path $Output).Path
$Vcpkg = Join-Path $WorkDir "vcpkg"
$VcpkgCommit = [string]$Config.portable.vcpkg_commit
if ($VcpkgCommit -notmatch '^[a-f0-9]{40}$') { throw "Invalid pinned vcpkg commit" }
if (-not (Test-Path (Join-Path $Vcpkg ".git"))) {
    Invoke-Checked git init $Vcpkg
    Invoke-Checked git -C $Vcpkg remote add origin https://github.com/microsoft/vcpkg.git
}
Invoke-Checked git -C $Vcpkg fetch --depth=1 origin $VcpkgCommit
Invoke-Checked git -C $Vcpkg checkout --detach $VcpkgCommit
if ((& git -C $Vcpkg rev-parse HEAD).Trim() -ne $VcpkgCommit) { throw "vcpkg pin mismatch" }
Invoke-Checked (Join-Path $Vcpkg "bootstrap-vcpkg.bat") -disableMetrics
$env:VCPKG_MAX_CONCURRENCY = [string]$Parallel
# OpenSSL and zlib are linked statically into tdjson.dll; the CRT uses standard /MD.
Invoke-Checked (Join-Path $Vcpkg "vcpkg.exe") install openssl:x64-windows-static-md zlib:x64-windows-static-md gperf:x64-windows --disable-metrics
$env:PATH = "$(Join-Path $Vcpkg 'installed/x64-windows/tools/gperf');$env:PATH"
if (-not (Get-Command gperf -ErrorAction SilentlyContinue)) { throw "vcpkg gperf was not installed" }
$Build = Join-Path $WorkDir "tdlib-$Commit"
Invoke-Checked cmake -S $Source -B $Build -G "Visual Studio 17 2022" -A x64 `
    "-DCMAKE_TOOLCHAIN_FILE=$Vcpkg/scripts/buildsystems/vcpkg.cmake" `
    -DVCPKG_TARGET_TRIPLET=x64-windows-static-md -DCMAKE_BUILD_TYPE=Release `
    -DTD_INSTALL_STATIC_LIBRARIES=OFF -DTD_INSTALL_SHARED_LIBRARIES=ON `
    -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL -DOPENSSL_USE_STATIC_LIBS=TRUE `
    -DBUILD_TESTING=OFF "-DCMAKE_INSTALL_PREFIX=$Output"
Invoke-Checked cmake --build $Build --config Release --target tdjson --parallel $Parallel
Invoke-Checked cmake --install $Build --config Release
$Library = Join-Path $Output "bin/tdjson.dll"
if (-not (Test-Path $Library)) { throw "Expected tdjson.dll was not produced" }
Invoke-Checked python (Join-Path $PSScriptRoot "smoke-portable.py") $Library
$Licenses = Join-Path $Output "licenses"
New-Item -ItemType Directory -Force -Path $Licenses | Out-Null
foreach ($Port in @("openssl", "zlib")) {
    Copy-Item (Join-Path $Vcpkg "installed/x64-windows-static-md/share/$Port/copyright") (Join-Path $Licenses "$Port.txt")
}
Copy-Item (Join-Path $Source "td/generate/scheme/td_api.tl") (Join-Path $Output "td_api.tl")
$BuildInfo = Join-Path $WorkDir "build-info.json"
@{
    compiler = "Visual Studio 2022 MSVC x64"; configuration = "Release"
    vcpkg = @{release = $Config.portable.vcpkg_release; commit = $VcpkgCommit; triplet = "x64-windows-static-md"}
    dependencies = @{openssl = (Get-Content (Join-Path $Vcpkg "ports/openssl/vcpkg.json") -Raw | ConvertFrom-Json); zlib = (Get-Content (Join-Path $Vcpkg "ports/zlib/vcpkg.json") -Raw | ConvertFrom-Json)}
    runtime = "Windows x64 with Microsoft Visual C++ 2015-2022 x64 Redistributable"
    smoke_test = "Loaded tdjson.dll and executed getTextEntities without a Telegram account"
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $BuildInfo
Invoke-Checked python (Join-Path $PSScriptRoot "package-common.py") --source $Source --root $Output --platform windows-x64 --build-json $BuildInfo
Write-Host "Windows x64 package ready: $Output"
