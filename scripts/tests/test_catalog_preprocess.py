from pathlib import Path

import pytest

from batch.catalog import build_catalog, discover_mat_files


def test_preprocess_catalog_builds_txt_and_csv():
    pytest.importorskip("scipy")
    pytest.importorskip("pandas")

    root = Path(__file__).resolve().parent
    mat_dir = root / "data"
    out_dir = root / "data" / "normalized"

    if not mat_dir.exists():
        pytest.skip(f"No existe {mat_dir}")

    mats = discover_mat_files(mat_dir)
    if not mats:
        pytest.skip(f"No hay .mat en {mat_dir}")

    df = build_catalog(mats, out_dir, units="m/s2")

    assert len(df.index) >= 1
    ok_rows = df[df["status_preprocess"] == "OK"]
    assert not ok_rows.empty
    row = ok_rows.iloc[0]
    assert Path(row["x_txt_path"]).exists()
    assert Path(row["y_txt_path"]).exists()
    assert (root / "results" / "catalog.csv").exists()
