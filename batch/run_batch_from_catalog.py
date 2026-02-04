from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pandas.errors import EmptyDataError

from solvers.sap2000.nlth import create_or_update_th_function_from_file
from solvers.sap2000.nlth_case import create_or_update_nlth_case
from solvers.sap2000.analysis import get_case_status_map
from solvers.sap2000.results_setup import select_case_for_output
from solvers.sap2000.edp_nodes import get_node_displacements_with_histories
from solvers.sap2000.edp_drift import compute_consecutive_drifts
from inputs.nodes_config import load_nodes_config
from solvers.sap2000.units import set_present_units, accel_scale_from_units
from persistence.sqlite_store import (
    init_db,
    insert_run,
    insert_node_disp,
    insert_drifts,
    insert_summary,
)


def _load_existing_results(results_path: Path) -> pd.DataFrame:
    print(f"[batch] Cargando resultados existentes: {results_path}")
    if results_path.exists():
        try:
            return pd.read_csv(results_path)
        except EmptyDataError:
            return pd.DataFrame()
    return pd.DataFrame(
        columns=[
            "record_id",
            "finished",
            "ret_getcasestatus",
            "status_code",
            "dt",
            "n_steps",
            "x_txt_path",
            "y_txt_path",
            "max_drift_u1",
            "max_drift_u2",
            "max_disp_u1",
            "max_disp_u2",
            "error",
        ]
    )


def run_batch_from_catalog(
    sap_model,
    catalog_csv,
    case_name="NLTH_BATCH",
    overwrite_functions=True,
    resume=True,
    overwrite_results=True,
    base_dir=None,
):
    print("[batch] Iniciando run_batch_from_catalog")
    catalog_path = Path(catalog_csv).resolve()
    if not catalog_path.exists():
        raise FileNotFoundError(catalog_path)

    print(f"[batch] Catalogo: {catalog_path}")
    config_path = Path("config").resolve() / "settings.yaml"
    print(f"[batch] Config nodes: {config_path}")
    _case_name_cfg, _model_path, output_time_step, nodes, nlth_case_config, overwrite_db, output_units, accel_in_g = load_nodes_config(config_path)
    db_path = Path("results").resolve() / "edp.sqlite"
    print(f"[batch] DB: {db_path}")
    if overwrite_db and db_path.exists():
        print(f"[batch] Overwrite DB: eliminando {db_path}")
        db_path.unlink()
    init_db(db_path)
    print(f"[batch] Unidades de salida: {output_units}")
    set_present_units(sap_model, output_units)
    accel_scale = accel_scale_from_units(output_units, accel_in_g=accel_in_g)
    print(f"[batch] Escala acelerograma (g -> unidades): {accel_scale}")

    catalog = pd.read_csv(catalog_path)
    print(f"[batch] Registros en catalogo: {len(catalog.index)}")
    results_path = Path("results").resolve() / "batch_results.csv"
    if overwrite_results and results_path.exists():
        print(f"[batch] Eliminando resultados previos: {results_path}")
        results_path.unlink()
    existing = _load_existing_results(results_path)
    print(f"[batch] Resultados existentes: {len(existing.index)}")

    finished_ids = set()
    if resume and not existing.empty:
        finished_ids = set(
            existing.loc[existing["finished"] == True, "record_id"].tolist()
        )
    print(f"[batch] Resume={resume} Finished_ids={len(finished_ids)}")

    results_rows = []
    total = len(catalog.index)

    for idx, row in catalog.iterrows():
        record_id = str(row["record_id"])
        if resume and record_id in finished_ids:
            print(f"[batch] Skip {record_id} (finished)")
            continue

        print(f"[{idx + 1}/{total}] {record_id}")

        error = ""
        finished = False
        status_code = None
        ret_getcasestatus = None

        try:
            if row.get("status_preprocess") != "OK":
                raise RuntimeError("Registro con preproceso fallido")

            def _resolve_path(path_value: str) -> Path:
                raw = Path(path_value)
                if raw.is_absolute():
                    return raw
                if base_dir is None:
                    base = catalog_path.parent.parent
                else:
                    base = Path(base_dir)
                return (base / raw).resolve()

            x_txt = _resolve_path(row["x_txt_path"])
            y_txt = _resolve_path(row["y_txt_path"])
            dt = float(row["dt"])
            n_steps = int(row["n_steps"])
            duration = dt * n_steps
            output_steps = max(1, int(round(duration / output_time_step)))

            func_x = f"TH_{record_id}_X"
            func_y = f"TH_{record_id}_Y"

            if overwrite_functions:
                print(f"  [batch] Creando funciones TH para {record_id}")
                create_or_update_th_function_from_file(
                    sap_model,
                    func_name=func_x,
                    file_path=str(x_txt),
                    dt=dt
                )
                create_or_update_th_function_from_file(
                    sap_model,
                    func_name=func_y,
                    file_path=str(y_txt),
                    dt=dt
                )

            print(f"  [batch] Creando/actualizando caso {case_name}")
            nlth_kwargs = dict(
                case_name=case_name,
                func_x=func_x,
                func_y=func_y,
                scale_x=accel_scale,
                scale_y=accel_scale,
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
            try:
                create_or_update_nlth_case(sap_model, **nlth_kwargs)
            except TypeError:
                # Backward compatibility with older nlth_case signature.
                nlth_kwargs.pop("initial_case", None)
                nlth_kwargs.pop("p_delta", None)
                create_or_update_nlth_case(sap_model, **nlth_kwargs)

            print("  [batch] Ejecutando analisis")
            sap_model.Analyze.RunAnalysis()

            print("  [batch] Consultando estado del caso")
            case_dict, ret = get_case_status_map(sap_model)
            ret_getcasestatus = ret
            if ret != 0:
                raise RuntimeError("Error llamando a GetCaseStatus")

            if case_name not in case_dict:
                raise RuntimeError(f"Caso {case_name} no encontrado")

            status_code = int(case_dict[case_name])
            finished = status_code == 4
            print(f"  Estado caso {case_name}: {status_code} (Finished={finished})")

        except Exception as exc:
            error = str(exc)
            print(f"  Error: {error}")

        results_rows.append(
            {
                "record_id": record_id,
                "finished": finished,
                "ret_getcasestatus": ret_getcasestatus,
                "status_code": status_code,
                "dt": row.get("dt"),
                "n_steps": row.get("n_steps"),
                "x_txt_path": row.get("x_txt_path"),
                "y_txt_path": row.get("y_txt_path"),
                "max_drift_u1": None,
                "max_drift_u2": None,
                "max_disp_u1": None,
                "max_disp_u2": None,
                "error": error,
            }
        )

        run_id = insert_run(
            db_path,
            record_id=record_id,
            case_name=case_name,
            dt=row.get("dt"),
            n_steps=row.get("n_steps"),
            finished=finished,
            error=error,
        )
        print(f"  [batch] run_id={run_id}")

        if finished and not error:
            try:
                print("  [batch] Extrayendo EDPs")
                select_case_for_output(sap_model, case_name)
                df_nodes, node_histories = get_node_displacements_with_histories(
                    sap_model, nodes
                )
                df_drifts, summary = compute_consecutive_drifts(
                    node_histories=node_histories
                )
                max_drift_u1 = None
                max_drift_u2 = None
                if df_drifts is not None and not df_drifts.empty:
                    max_drift_u1 = float(df_drifts["drift_u1"].abs().max())
                    max_drift_u2 = float(df_drifts["drift_u2"].abs().max())

                max_disp_u1 = None
                max_disp_u2 = None
                if df_nodes is not None and not df_nodes.empty:
                    max_u1 = df_nodes["u1_max"].abs().max()
                    min_u1 = df_nodes["u1_min"].abs().max()
                    max_u2 = df_nodes["u2_max"].abs().max()
                    min_u2 = df_nodes["u2_min"].abs().max()
                    max_disp_u1 = float(max(max_u1, min_u1))
                    max_disp_u2 = float(max(max_u2, min_u2))

                results_rows[-1]["max_drift_u1"] = max_drift_u1
                results_rows[-1]["max_drift_u2"] = max_drift_u2
                results_rows[-1]["max_disp_u1"] = max_disp_u1
                results_rows[-1]["max_disp_u2"] = max_disp_u2
                print("  [batch] Guardando EDPs en SQLite")
                insert_node_disp(db_path, run_id, df_nodes)
                insert_drifts(db_path, run_id, df_drifts)
                insert_summary(db_path, run_id, summary)
            except Exception as exc:
                print(f"  Error extrayendo EDPs: {exc}")

        updated = pd.concat(
            [existing, pd.DataFrame(results_rows)],
            ignore_index=True
        )
        results_path.parent.mkdir(parents=True, exist_ok=True)
        updated.to_csv(results_path, index=False)

    final_df = pd.concat(
        [existing, pd.DataFrame(results_rows)],
        ignore_index=True
    )
    return final_df
