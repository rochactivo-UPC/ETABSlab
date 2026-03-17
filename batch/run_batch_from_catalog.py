from pathlib import Path
import sys
import json
import builtins
from datetime import datetime

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
from solvers.sap2000.edp_energy import get_link_energy
from solvers.sap2000.edp_base_reaction import get_base_reaction_envelope
from inputs.nodes_config import load_nodes_config
from solvers.sap2000.units import set_present_units, accel_scale_from_units
from persistence.sqlite_store import (
    init_db,
    insert_run,
    insert_node_disp,
    insert_drifts,
    insert_summary,
    insert_link_energy,
)


def print(*args, **kwargs):  # noqa: A001
    kwargs.setdefault("flush", True)
    return builtins.print(*args, **kwargs)


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
            "max_vx_base",
            "max_vy_base",
            "min_vx_base",
            "min_vy_base",
            "energy_link_max",
            "energy_link_final",
            "error",
        ]
    )


def _load_checkpoint(checkpoint_path: Path) -> dict:
    if not checkpoint_path.exists():
        return {}
    try:
        with checkpoint_path.open("r", encoding="utf-8") as handle:
            return json.load(handle) or {}
    except Exception:
        return {}


def _save_checkpoint(checkpoint_path: Path, payload: dict):
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
    with checkpoint_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _maybe_clear_results(sap_model):
    method = getattr(sap_model.Analyze, "DeleteAnalysisResults", None)
    if method is None:
        return False
    try:
        ret = method()
    except Exception:
        return False
    return ret == 0


def _ret_code(ret):
    if isinstance(ret, (list, tuple)):
        return ret[-1] if ret else 0
    return ret


def _set_run_case_flag(sap_model, case_name: str, do_run: bool) -> bool:
    method = getattr(sap_model.Analyze, "SetRunCaseFlag", None)
    if method is None:
        return False
    attempts = [
        (case_name, do_run, False),
        (case_name, do_run),
    ]
    for args in attempts:
        try:
            if _ret_code(method(*args)) == 0:
                return True
        except Exception:
            continue
    return False


def _set_only_case_to_run(sap_model, case_name: str):
    try:
        _n, names, _status, ret = sap_model.Analyze.GetCaseStatus()
        if ret == 0 and isinstance(names, (list, tuple)):
            for name in names:
                _set_run_case_flag(sap_model, str(name), False)
    except Exception:
        pass
    if not _set_run_case_flag(sap_model, case_name, True):
        print(f"  [batch] Aviso: no se pudo forzar run flag para {case_name}; SAP usara su seleccion actual.")


def _enforce_ping_pong_run_target(
    sap_model,
    target_case: str,
    ping_case_a: str,
    ping_case_b: str,
    initial_gravity_case: str,
):
    # Guarantee only the target case runs for this step.
    for name in {str(ping_case_a).strip(), str(ping_case_b).strip(), str(initial_gravity_case).strip()}:
        if name:
            _set_run_case_flag(sap_model, name, False)
    if not _set_run_case_flag(sap_model, target_case, True):
        print(f"  [batch] Aviso: no se pudo forzar run flag para {target_case}; SAP usara su seleccion actual.")


def _case_exists(sap_model, case_name: str) -> bool:
    try:
        result = sap_model.LoadCases.GetNameList()
    except Exception:
        return False
    if not isinstance(result, (list, tuple)):
        return False
    names = None
    for item in result:
        if isinstance(item, (list, tuple)):
            names = item
            break
    if names is None:
        return False
    return case_name in names


def _set_initial_case_best_effort(sap_model, case_name: str, initial_case: str) -> bool:
    method = getattr(sap_model.LoadCases.DirHistNonlinear, "SetInitialCase", None)
    if method is None:
        return False
    if not _case_exists(sap_model, case_name):
        return False
    init_name = "" if not str(initial_case).strip() else str(initial_case)
    try:
        ret = method(case_name, init_name)
    except Exception:
        return False
    return ret == 0


def _copy_case_best_effort(sap_model, source_case: str, target_case: str) -> bool:
    load_cases = getattr(sap_model, "LoadCases", None)
    if load_cases is None:
        return False
    attempts = [
        ("Copy", (source_case, target_case)),
        ("CopyCase", (source_case, target_case)),
        ("Duplicate", (source_case, target_case)),
    ]
    for method_name, args in attempts:
        method = getattr(load_cases, method_name, None)
        if method is None:
            continue
        try:
            if _ret_code(method(*args)) == 0:
                return True
        except Exception:
            continue
    return False


def run_batch_from_catalog(
    sap_model,
    catalog_csv,
    case_name="NLTH_BATCH",
    overwrite_functions=True,
    resume=True,
    overwrite_results=True,
    base_dir=None,
    settings_path=None,
    results_dir=None,
    normalized_dir=None,
):
    print("[batch] Iniciando run_batch_from_catalog")
    catalog_path = Path(catalog_csv).resolve()
    if not catalog_path.exists():
        raise FileNotFoundError(catalog_path)

    print(f"[batch] Catalogo: {catalog_path}")
    root_dir = Path(base_dir).resolve() if base_dir is not None else catalog_path.parent.parent.resolve()
    config_path = Path(settings_path).resolve() if settings_path is not None else (root_dir / "config" / "settings.yaml").resolve()
    results_root = Path(results_dir).resolve() if results_dir is not None else (root_dir / "results").resolve()
    normalized_root = Path(normalized_dir).resolve() if normalized_dir is not None else (root_dir / "data" / "normalized").resolve()
    results_root.mkdir(parents=True, exist_ok=True)
    print(f"[batch] Config nodes: {config_path}")
    (
        case_name_cfg,
        _model_path,
        output_time_step,
        nodes,
        nlth_case_config,
        overwrite_db,
        output_units,
        accel_in_g,
        use_ping_pong,
        ping_pong_cases,
        use_chain_series,
        chain_case_prefix,
        checkpoint_every,
        clear_results_after_edp,
        initial_gravity_case,
        energy_link,
        enable_link_energy,
        energy_component,
        energy_point_elm,
        energy_mode,
    ) = load_nodes_config(config_path)
    if use_ping_pong and use_chain_series:
        raise ValueError("settings.yaml: use_ping_pong y use_chain_series no pueden estar activos a la vez")
    if (use_ping_pong or use_chain_series) and clear_results_after_edp:
        mode_name = "use_chain_series" if use_chain_series else "use_ping_pong"
        print(f"[batch] Aviso: {mode_name}=True fuerza clear_results_after_edp=False para mantener la cadena de estados.")
        clear_results_after_edp = False
    db_path = (results_root / "edp.sqlite").resolve()
    print(f"[batch] DB: {db_path}")
    if overwrite_db and db_path.exists():
        print(f"[batch] Overwrite DB: eliminando {db_path}")
        db_path.unlink()
    init_db(db_path)
    print(f"[batch] Unidades de salida: {output_units}")
    set_present_units(sap_model, output_units)
    accel_scale = accel_scale_from_units(output_units, accel_in_g=accel_in_g)
    print(f"[batch] Escala acelerograma (g -> unidades): {accel_scale}")

    catalog = pd.read_csv(catalog_path).reset_index(drop=True)
    print(f"[batch] Registros en catalogo: {len(catalog.index)}")
    results_path = (results_root / "batch_results.csv").resolve()
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

    checkpoint_path = (results_root / "checkpoint.json").resolve()
    checkpoint = _load_checkpoint(checkpoint_path) if resume else {}
    start_index = int(checkpoint.get("last_index", -1)) + 1 if checkpoint else 0
    last_finished_case = str(checkpoint.get("last_finished_case", "")) if checkpoint else ""
    ping_case_a = str(ping_pong_cases[0]).strip() if use_ping_pong else ""
    ping_case_b = str(ping_pong_cases[1]).strip() if use_ping_pong else ""

    for idx, row in catalog.iterrows():
        if resume and idx < start_index:
            continue
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
                raw = Path(str(path_value).strip())
                if raw.is_absolute():
                    if raw.exists():
                        return raw
                    alt = (normalized_root / raw.name).resolve()
                    if alt.exists():
                        return alt
                    return raw

                base_candidates = [
                    (Path(base_dir).resolve() if base_dir is not None else None),
                    catalog_path.parent.resolve(),
                    catalog_path.parent.parent.resolve(),
                    results_root.resolve(),
                    normalized_root.resolve(),
                ]
                for base in base_candidates:
                    if base is None:
                        continue
                    candidate = (base / raw).resolve()
                    if candidate.exists():
                        return candidate

                by_name = (normalized_root / raw.name).resolve()
                if by_name.exists():
                    return by_name

                # Keep deterministic fallback for error reporting.
                if base_dir is not None:
                    return (Path(base_dir).resolve() / raw).resolve()
                return (catalog_path.parent.resolve() / raw).resolve()

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

            if use_chain_series:
                case_name = f"{chain_case_prefix}_{idx + 1:04d}_{record_id}"
            elif use_ping_pong:
                if not last_finished_case:
                    case_name = ping_case_a
                elif last_finished_case == ping_case_a:
                    case_name = ping_case_b
                elif last_finished_case == ping_case_b:
                    case_name = ping_case_a
                else:
                    print(
                        f"  [batch] Aviso: last_finished_case inesperado '{last_finished_case}', reiniciando secuencia en {ping_case_a}"
                    )
                    case_name = ping_case_a
            current_initial_case = None
            if use_chain_series:
                if last_finished_case:
                    current_initial_case = last_finished_case
                else:
                    current_initial_case = initial_gravity_case
                print(f"  [batch] Chain: {current_initial_case} -> {case_name}")
            elif use_ping_pong:
                if last_finished_case:
                    current_initial_case = last_finished_case
                else:
                    current_initial_case = initial_gravity_case
                print(f"  [batch] Secuencia: {current_initial_case} -> {case_name}")

            print(f"  [batch] Creando/actualizando caso {case_name}")
            if use_chain_series and not last_finished_case:
                cloned = _copy_case_best_effort(sap_model, case_name_cfg, case_name)
                print(f"  [batch] Clon base {case_name_cfg} -> {case_name}: {cloned}")
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
                initial_case=current_initial_case,
            )
            try:
                create_or_update_nlth_case(sap_model, **nlth_kwargs)
            except TypeError:
                # Backward compatibility with older nlth_case signature.
                nlth_kwargs.pop("initial_case", None)
                nlth_kwargs.pop("p_delta", None)
                create_or_update_nlth_case(sap_model, **nlth_kwargs)

            if use_chain_series:
                _set_only_case_to_run(sap_model, case_name)
            elif use_ping_pong:
                _enforce_ping_pong_run_target(
                    sap_model,
                    target_case=case_name,
                    ping_case_a=ping_case_a,
                    ping_case_b=ping_case_b,
                    initial_gravity_case=initial_gravity_case,
                )

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
                "max_vx_base": None,
                "max_vy_base": None,
                "min_vx_base": None,
                "min_vy_base": None,
                "energy_link_max": None,
                "energy_link_final": None,
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
                try:
                    base_reaction = get_base_reaction_envelope(sap_model)
                    results_rows[-1]["max_vx_base"] = base_reaction.get("max_vx")
                    results_rows[-1]["max_vy_base"] = base_reaction.get("max_vy")
                    results_rows[-1]["min_vx_base"] = base_reaction.get("min_vx")
                    results_rows[-1]["min_vy_base"] = base_reaction.get("min_vy")
                except Exception as exc:
                    print(f"  Error extrayendo base reaction: {exc}")
                    base_reaction = None
                print("  [batch] Guardando EDPs en SQLite")
                if base_reaction:
                    summary["max_vx_base"] = base_reaction.get("max_vx")
                    summary["max_vy_base"] = base_reaction.get("max_vy")
                    summary["min_vx_base"] = base_reaction.get("min_vx")
                    summary["min_vy_base"] = base_reaction.get("min_vy")
                insert_node_disp(db_path, run_id, df_nodes)
                insert_drifts(db_path, run_id, df_drifts)
                insert_summary(db_path, run_id, summary)

                if enable_link_energy and energy_link:
                    print(f"  [batch] Extrayendo energia link: {energy_link}")
                    energy = get_link_energy(
                        sap_model,
                        energy_link,
                        energy_component,
                        energy_point_elm,
                        energy_mode=energy_mode,
                    )
                    if energy:
                        results_rows[-1]["energy_link_max"] = energy.get("max")
                        results_rows[-1]["energy_link_final"] = energy.get("final")
                        insert_link_energy(
                            db_path,
                            run_id,
                            energy_link,
                            energy_component,
                            energy_point_elm,
                            energy,
                        )
                elif not enable_link_energy:
                    print("  [batch] Energia link desactivada por config")
            except Exception as exc:
                print(f"  Error extrayendo EDPs: {exc}")

        if finished and not error:
            last_finished_case = case_name

        if clear_results_after_edp and finished and not error:
            cleared = _maybe_clear_results(sap_model)
            print(f"  [batch] Limpieza resultados: {cleared}")

        updated = pd.concat(
            [existing, pd.DataFrame(results_rows)],
            ignore_index=True
        )
        results_path.parent.mkdir(parents=True, exist_ok=True)
        updated.to_csv(results_path, index=False)

        if checkpoint_every > 0 and ((idx + 1) % checkpoint_every == 0):
            _save_checkpoint(
                checkpoint_path,
                {
                    "last_index": idx,
                    "last_record_id": record_id,
                    "last_finished_case": last_finished_case,
                    "use_ping_pong": bool(use_ping_pong),
                    "use_chain_series": bool(use_chain_series),
                },
            )

    final_df = pd.concat(
        [existing, pd.DataFrame(results_rows)],
        ignore_index=True
    )
    if checkpoint_every > 0:
        _save_checkpoint(
            checkpoint_path,
            {
                "last_index": total - 1,
                "last_record_id": str(catalog.iloc[-1]["record_id"])
                if total > 0
                else "",
                "last_finished_case": last_finished_case,
                "use_ping_pong": bool(use_ping_pong),
                "use_chain_series": bool(use_chain_series),
            },
        )
    return final_df
