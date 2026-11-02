$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    & python scripts/apply_patches.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $modules = @('mangascantrad', 'mangakawaii', 'animesama', 'aniverse', 'japscan')
    $checks = @(':core:lintRelease', ':lib-multisrc:madara:lintRelease')
    $checks += $modules | ForEach-Object { ":src:fr:${_}:lintRelease" }
    & ./gradlew.bat --no-daemon @checks
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $builds = $modules | ForEach-Object { ":src:fr:${_}:assembleRelease" }
    & ./gradlew.bat --no-daemon @builds
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
