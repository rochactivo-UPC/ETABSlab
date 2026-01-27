param(
    [string]$OutRoot = "C:\Users\rocha\Documents\ETABSlab_exe"
)

$ErrorActionPreference = "Stop"

$dist = Join-Path $OutRoot "dist"
$build = Join-Path $OutRoot "build"
$spec = Join-Path $OutRoot "spec"

New-Item -ItemType Directory -Force -Path $dist, $build, $spec | Out-Null

pyinstaller --onefile --name etabslab_batch `
  --distpath $dist `
  --workpath $build `
  --specpath $spec `
  scripts\run_nlth_batch.py
