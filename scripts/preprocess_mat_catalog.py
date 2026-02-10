from pathlib import Path
import sys
import argparse
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from batch.catalog import discover_mat_files, build_catalog

DEFAULT_UNITS = "gal"


def _parse_args():
    parser = argparse.ArgumentParser(description="Preprocesa .mat y genera catalogo CSV")
    parser.add_argument("--settings", dest="settings", default=None, help="Ruta a settings.yaml")
    return parser.parse_args()


def _resolve_path_value(raw_value: str | None, default_path: Path, root_dir: Path) -> Path:
    if not raw_value:
        return default_path.resolve()
    candidate = Path(str(raw_value).strip())
    if candidate.is_absolute():
        return candidate.resolve()
    return (root_dir / candidate).resolve()


def main():
    args = _parse_args()
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent
    else:
        root = Path(__file__).resolve().parents[1]
    settings_path = Path(args.settings).resolve() if args.settings else (root / "config" / "settings.yaml").resolve()
    settings_data = {}
    if settings_path.exists():
        with settings_path.open("r", encoding="utf-8") as handle:
            settings_data = yaml.safe_load(handle) or {}
    settings_root = settings_path.parent.resolve() if settings_path.exists() else root

    mat_dir = _resolve_path_value(settings_data.get("mat_dir"), root / "data" / "mat", settings_root)
    mat_dir.mkdir(parents=True, exist_ok=True)

    out_dir = _resolve_path_value(settings_data.get("normalized_dir"), root / "data" / "normalized", settings_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_dir = _resolve_path_value(settings_data.get("results_dir"), root / "results", settings_root)
    results_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = _resolve_path_value(settings_data.get("catalog_path"), results_dir / "catalog.csv", settings_root)
    units = str(settings_data.get("input_units", DEFAULT_UNITS))

    mat_files = discover_mat_files(mat_dir)
    if not mat_files:
        print(f"No se encontraron .mat en {mat_dir}")
        return

    build_catalog(mat_files, out_dir, units=units, catalog_path=catalog_path)
    print(f"Catalogo generado en {catalog_path}")


if __name__ == "__main__":
    main()
