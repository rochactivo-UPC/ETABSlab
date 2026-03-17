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

pyinstaller --onefile --name etabslab_preprocess `
  --distpath $dist `
  --workpath $build `
  --specpath $spec `
  scripts\preprocess_mat_catalog.py

pyinstaller --onefile --name etabslab_inspect `
  --distpath $dist `
  --workpath $build `
  --specpath $spec `
  scripts\inspect_db.py

pyinstaller --onefile --name etabslab_energy `
  --distpath $dist `
  --workpath $build `
  --specpath $spec `
  scripts\inspect_link_energy.py

pyinstaller --onefile --windowed --name etabslab_gui `
  --icon EQLab.ico `
  --distpath $dist `
  --workpath $build `
  --specpath $spec `
  scripts\gui_settings_runner.py
