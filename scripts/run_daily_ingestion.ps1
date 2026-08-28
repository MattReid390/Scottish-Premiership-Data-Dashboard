# Wrapper for Windows Task Scheduler: activates the project's virtual
# environment and runs the daily ingestion job. See
# docs/data_ingestion.md section 5 and docs/environment_configuration.md.
#
# Task Scheduler runs actions with no shell profile and an arbitrary
# working directory, so this resolves the project root from its own
# location rather than assuming the caller's cwd, and calls the venv's
# python.exe directly rather than relying on `activate` having been run.

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

& "$ProjectRoot\.venv\Scripts\python.exe" -m src.run_daily_ingestion
exit $LASTEXITCODE
