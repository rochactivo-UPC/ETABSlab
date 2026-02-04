from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs.nodes_config import load_nodes_config
from solvers.sap2000.connect import Sap2000Connection
from solvers.sap2000.model_checks import check_model_loaded_and_unlocked
from solvers.sap2000.results_setup import select_case_for_output
from solvers.sap2000.nlth import create_or_update_th_function_from_file
from solvers.sap2000.nlth_case import create_or_update_nlth_case


MODEL_PATH = None
CASE_NAME = None


def _open_model(conn, model_path: str):
    model_path = Path(model_path).resolve()
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    conn.open_model(str(model_path))


def _get_if_exists(api, method_name, *args):
    method = getattr(api, method_name, None)
    if method is None:
        return None
    try:
        return method(*args)
    except Exception as exc:
        return f"ERR: {type(exc).__name__}: {exc}"


def _snapshot_case(sap_model, case_name: str):
    api = sap_model.LoadCases.DirHistNonlinear
    return {
        "time_integration": _get_if_exists(api, "GetTimeIntegration", case_name),
        "sol_control": _get_if_exists(api, "GetSolControlParameters", case_name),
        "damp_proportional": _get_if_exists(api, "GetDampProportional", case_name),
        "time_step": _get_if_exists(api, "GetTimeStep", case_name),
        "loads": _get_if_exists(api, "GetLoads", case_name),
    }


def _print_snapshot(label, snap):
    print(f"\n--- {label} ---")
    for key, value in snap.items():
        print(f"{key}: {value}")


def _load_first_catalog_row(base_dir: Path):
    catalog_path = base_dir / "results" / "catalog.csv"
    if not catalog_path.exists():
        raise FileNotFoundError(catalog_path)
    catalog = pd.read_csv(catalog_path)
    if catalog.empty:
        raise RuntimeError("catalog.csv vacio")
    row = catalog.iloc[0]
    return row, catalog_path


def main():
    base_dir = Path(__file__).resolve().parents[2]
    config_path = base_dir / "config" / "settings.yaml"
    case_name, model_path, output_time_step, _nodes, nlth_case_config, _overwrite_db, _output_units, _accel_in_g = load_nodes_config(
        config_path
    )
    target_case = CASE_NAME or case_name
    target_model_path = MODEL_PATH or model_path

    row, catalog_path = _load_first_catalog_row(base_dir)
    dt = float(row["dt"])
    n_steps = int(row["n_steps"])
    duration = dt * n_steps
    output_steps = max(1, int(round(duration / output_time_step)))

    def _resolve_path(path_value: str) -> Path:
        raw = Path(path_value)
        if raw.is_absolute():
            return raw
        return (catalog_path.parent.parent / raw).resolve()

    x_txt = _resolve_path(row["x_txt_path"])
    y_txt = _resolve_path(row["y_txt_path"])
    func_x = f"TH_{row['record_id']}_X_TEST"
    func_y = f"TH_{row['record_id']}_Y_TEST"

    conn = Sap2000Connection()
    sap_model = conn.connect()
    if target_model_path:
        _open_model(conn, target_model_path)

    check_model_loaded_and_unlocked(sap_model, target_model_path, allow_locked=True)

    print("Creando/actualizando funciones TH...")
    create_or_update_th_function_from_file(
        sap_model,
        func_name=func_x,
        file_path=str(x_txt),
        dt=dt,
    )
    create_or_update_th_function_from_file(
        sap_model,
        func_name=func_y,
        file_path=str(y_txt),
        dt=dt,
    )

    print("Snapshot antes de crear/actualizar caso:")
    _print_snapshot("before", _snapshot_case(sap_model, target_case))

    print("Creando caso (aplicando parametros del YAML)...")
    create_or_update_nlth_case(
        sap_model,
        case_name=target_case,
        func_x=func_x,
        func_y=func_y,
        dt=dt,
        n_steps=n_steps,
        output_time_step=output_time_step,
        output_steps=output_steps,
        p_delta=nlth_case_config.get("p_delta", True),
        apply_parameters=nlth_case_config.get("apply_parameters", True),
        damping=nlth_case_config.get("damping"),
        time_integration=nlth_case_config.get("time_integration"),
        nonlinear_parameters=nlth_case_config.get("nonlinear_parameters"),
        initial_conditions=nlth_case_config.get("initial_conditions"),
        initial_case=nlth_case_config.get("initial_case", "NL DL+0.25LL"),
    )

    _print_snapshot("after create", _snapshot_case(sap_model, target_case))

    print("Actualizando solo loads y output steps (apply_parameters=False)...")
    create_or_update_nlth_case(
        sap_model,
        case_name=target_case,
        func_x=func_x,
        func_y=func_y,
        dt=dt,
        n_steps=n_steps,
        output_time_step=output_time_step,
        output_steps=output_steps,
        p_delta=nlth_case_config.get("p_delta", True),
        apply_parameters=False,
        damping=None,
        time_integration=None,
        nonlinear_parameters=None,
        initial_conditions=None,
        initial_case=nlth_case_config.get("initial_case", "NL DL+0.25LL"),
    )

    _print_snapshot("after update", _snapshot_case(sap_model, target_case))

    select_case_for_output(sap_model, target_case)
    print("Listo. Revisa los snapshots para ver si cambian parametros.")


if __name__ == "__main__":
    main()
