# Local-first Blender XR checks and packaging. No GitHub runner needed.
param([switch]$Build)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
function Run-Python([string[]]$Arguments) {
    & python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "python $($Arguments -join ' ') failed with exit code $LASTEXITCODE" }
}
Push-Location $Root
try {
    Run-Python -Arguments @('-m', 'compileall', '-q', 'blender_xr', 'tests')
    Run-Python -Arguments @('tests/test_platform_support.py')
    Run-Python -Arguments @('tests/test_gestures.py')
    Run-Python -Arguments @('tests/test_prune.py')
    if ($Build) { Run-Python -Arguments @('scripts/build.py') }
    Write-Host "Local Blender-XR checks passed. GitHub Actions was not used."
} finally { Pop-Location }
