param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $PytestArgs = @("backend\tests", "tests", "-q")
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$localDeps = Join-Path $repoRoot ".deps\python"

$pythonCandidates = @()
$command = Get-Command python -ErrorAction SilentlyContinue
if ($command) {
    $pythonCandidates += $command.Source
}

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pyLauncher) {
    $pythonCandidates += $pyLauncher.Source
}

$codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path $codexPython) {
    $pythonCandidates += $codexPython
}

if (-not $pythonCandidates.Count) {
    throw "Python was not found. Install Python 3.12 or run this script in Codex Desktop."
}

$python = $pythonCandidates[0]
if (Test-Path $localDeps) {
    $env:PYTHONPATH = if ($env:PYTHONPATH) {
        "$localDeps;${env:PYTHONPATH}"
    } else {
        $localDeps
    }
}

Write-Host "Using Python: $python"
if (Test-Path $localDeps) {
    Write-Host "Using local dependencies: $localDeps"
}

& $python -m pytest @PytestArgs
exit $LASTEXITCODE
