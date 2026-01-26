from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from batch.catalog import discover_mat_files, build_catalog

DEFAULT_UNITS = "gal"


def main():
    root = Path(__file__).resolve().parents[1]
    mat_dir = root / "data" / "mat"
    mat_dir.mkdir(parents=True, exist_ok=True)

    out_dir = root / "data" / "normalized"
    out_dir.mkdir(parents=True, exist_ok=True)

    mat_files = discover_mat_files(mat_dir)
    if not mat_files:
        print(f"No se encontraron .mat en {mat_dir}")
        return

    build_catalog(mat_files, out_dir, units=DEFAULT_UNITS)
    print("Catalogo generado en results/catalog.csv")


if __name__ == "__main__":
    main()
