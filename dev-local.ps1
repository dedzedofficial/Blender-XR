# Local-first Blender XR checks and packaging. No GitHub runner needed.
# Examples:
#   .\dev-local.ps1 -Build
#   .\dev-local.ps1 -Build -BlenderPath 'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe'
param(
    [switch]$Build,
    [string]$BlenderPath
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Run-Python([string[]]$Arguments) {
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "python $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

Push-Location $Root
try {
    Run-Python -Arguments @('-m', 'compileall', '-q', 'blender_xr', 'tests')

    # These tests require only system Python, not a running Blender session.
    $PureTests = @(
        'test_platform_support.py', 'test_gestures.py', 'test_prune.py',
        'test_v080_controls.py', 'test_release_readiness.py'
    )
    foreach ($Name in $PureTests) {
        Run-Python -Arguments @("tests/$Name")
    }

    if ($Build) {
        Run-Python -Arguments @('scripts/build.py')
        Run-Python -Arguments @('tests/test_platform_package.py')
    }

    if ($BlenderPath) {
        if (-not (Test-Path -LiteralPath $BlenderPath -PathType Leaf)) {
            throw "Blender executable not found: $BlenderPath"
        }
        $BlenderExe = (Resolve-Path -LiteralPath $BlenderPath).ProviderPath
        & $BlenderExe --version
        if ($LASTEXITCODE -ne 0) {
            throw "Blender did not start: $BlenderExe"
        }

        # Each Blender integration script runs in its own fresh process to
        # prevent one test's scene, add-on registration or state leaking into
        # the next test. Do not run package-only tests inside Blender.
        $BlenderTests = @(Get-ChildItem -LiteralPath (Join-Path $Root 'tests') -File -Filter 'test_*.py' |
            Where-Object {
                ($PureTests -notcontains $_.Name) -and
                ($_.Name -ne 'test_platform_package.py')
            } | Sort-Object Name)
        foreach ($Test in $BlenderTests) {
            Write-Host "Blender integration: $($Test.Name)"
            & $BlenderExe --background --factory-startup --python-exit-code 1 --python $Test.FullName
            if ($LASTEXITCODE -ne 0) {
                throw "Blender integration failed: $($Test.Name) (exit $LASTEXITCODE)"
            }
        }
        Write-Host "Passed $($BlenderTests.Count) Blender integration scripts."
    }

    Write-Host 'Local Blender-XR validation passed. No GitHub Actions used.'
    if (-not $BlenderPath) {
        Write-Host 'Blender integration not run: supply -BlenderPath to test the add-on.'
    }
    if (-not $Build) {
        Write-Host 'Extension ZIP not built: supply -Build to verify packaging.'
    }
} finally {
    Pop-Location
}
