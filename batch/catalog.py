from pathlib import Path

import numpy as np

try:
    import pandas as pd
except Exception as exc:  # pragma: no cover - optional dependency at runtime
    pd = None
    _PANDAS_IMPORT_ERROR = exc

try:
    from scipy.io import loadmat
except Exception as exc:  # pragma: no cover - optional dependency at runtime
    loadmat = None
    _SCIPY_IMPORT_ERROR = exc

from experiments.accelerograms import mat_to_normalized


def discover_mat_files(mat_dir: str) -> list[Path]:
    mat_dir_path = Path(mat_dir).resolve()
    if not mat_dir_path.exists():
        return []

    mat_files = []
    for path in mat_dir_path.rglob("*.mat"):
        name = path.name
        if name.startswith("~$") or name.startswith(".~"):
            continue
        if name.endswith(".mat~") or name.endswith(".tmp"):
            continue
        mat_files.append(path)
    return mat_files


def sanitize_record_id(file_path: Path) -> str:
    stem = file_path.stem
    safe = stem.replace("(", "_").replace(")", "")
    safe = safe.replace(" ", "_")
    safe = safe.replace("__", "_")
    return safe


def _load_mat_once(mat_path: Path) -> dict:
    if loadmat is None:
        raise ImportError(
            f"Falta scipy. Instala con: pip install scipy ({_SCIPY_IMPORT_ERROR})"
        )
    return loadmat(mat_path)


def build_catalog(mat_files: list[Path], out_dir: Path, units="m/s2"):
    if pd is None:
        raise ImportError(
            f"Falta pandas. Instala con: pip install pandas ({_PANDAS_IMPORT_ERROR})"
        )

    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    total = len(mat_files)

    for idx, mat_path in enumerate(mat_files, start=1):
        record_id = sanitize_record_id(mat_path)
        mat_path = mat_path.resolve()
        x_key = "acc_f_e"
        y_key = "acc_f_n"
        x_txt_path = out_dir / f"{record_id}_E.txt"
        y_txt_path = out_dir / f"{record_id}_N.txt"
        mtime_mat = mat_path.stat().st_mtime

        status = "OK"
        error = ""
        dt_val = None
        n_steps = None

        print(f"[{idx}/{total}] {mat_path.name}")

        try:
            mat_data = _load_mat_once(mat_path)
            if x_key not in mat_data or y_key not in mat_data:
                raise KeyError(
                    f"Keys requeridas no encontradas: {x_key}, {y_key}"
                )

            acc_x = np.asarray(mat_data[x_key]).squeeze()
            acc_y = np.asarray(mat_data[y_key]).squeeze()
            n_steps = int(min(len(acc_x), len(acc_y)))

            if "dt" in mat_data:
                dt_val = float(np.asarray(mat_data["dt"]).squeeze().item())
            else:
                raise KeyError("Key requerida no encontrada: dt")

            cached = (
                x_txt_path.exists()
                and y_txt_path.exists()
                and x_txt_path.stat().st_mtime >= mtime_mat
                and y_txt_path.stat().st_mtime >= mtime_mat
            )

            if not cached:
                mat_to_normalized(
                    mat_path,
                    out_dir,
                    units=units,
                    acc_key=x_key,
                    acc_id=f"{record_id}_E",
                    dt_key="dt",
                    mat_data=mat_data
                )
                mat_to_normalized(
                    mat_path,
                    out_dir,
                    units=units,
                    acc_key=y_key,
                    acc_id=f"{record_id}_N",
                    dt_key="dt",
                    mat_data=mat_data
                )

        except Exception as exc:
            status = "FAIL"
            error = str(exc)
            print(f"  Error: {error}")

        rows.append(
            {
                "record_id": record_id,
                "mat_path": str(mat_path),
                "x_key": x_key,
                "y_key": y_key,
                "x_txt_path": str(x_txt_path.resolve()),
                "y_txt_path": str(y_txt_path.resolve()),
                "dt": dt_val,
                "n_steps": n_steps,
                "units": units,
                "status_preprocess": status,
                "error_preprocess": error,
                "mtime_mat": mtime_mat,
            }
        )

    df = pd.DataFrame(rows)

    results_dir = Path("results").resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = results_dir / "catalog.csv"
    df.to_csv(catalog_path, index=False)

    return df
