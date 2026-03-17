from pathlib import Path
import argparse
import sys

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs.nodes_config import load_nodes_config
from solvers.sap2000.connect import get_sap2000_model
from solvers.sap2000.analysis import get_case_status_map
from solvers.sap2000.model_checks import check_model_loaded_and_unlocked
from solvers.sap2000.nlth import create_or_update_th_function_from_file
from solvers.sap2000.nlth_case import create_or_update_nlth_case
from solvers.sap2000.units import set_present_units, accel_scale_from_units


def _ret_code(ret):
    if isinstance(ret, (list, tuple)):
        return ret[-1] if ret else 0
    return ret


def _open_model(sap_model, model_path: str):
    model = Path(model_path).resolve()
    if not model.exists():
        raise FileNotFoundError(model)
    ret = sap_model.File.OpenFile(str(model))
    if ret != 0:
        raise RuntimeError(f"No se pudo abrir el modelo SAP2000: {model}")


def _parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Prueba serie NLTH con casos nuevos por sismo, sin reciclar casos previos. "
            "Secuencia: Inicial -> Caso1 -> Caso2 -> ..."
        )
    )
    parser.add_argument(
        "--settings",
        default=str((ROOT / "config" / "settings.yaml").resolve()),
        help="Ruta al settings.yaml",
    )
    parser.add_argument(
        "--catalog",
        default=str((ROOT / "results" / "catalog_short.csv").resolve()),
        help="Ruta al catalogo CSV.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=6,
        help="Cantidad de sismos a ejecutar.",
    )
    parser.add_argument(
        "--case-prefix",
        default="NLTH_SER",
        help="Prefijo para los nuevos casos.",
    )
    return parser.parse_args()


def _resolve_path_value(raw_value: str | None, default_path: Path, root_dir: Path) -> Path:
    if not raw_value:
        return default_path.resolve()
    candidate = Path(str(raw_value).strip())
    if candidate.is_absolute():
        return candidate.resolve()
    return (root_dir / candidate).resolve()


def _load_settings_data(settings_path: Path) -> dict:
    if not settings_path.exists():
        return {}
    with settings_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _resolve_record_path(path_value: str, base_dir: Path, catalog_path: Path, results_dir: Path, normalized_dir: Path) -> Path:
    raw = Path(str(path_value).strip())
    if raw.is_absolute():
        if raw.exists():
            return raw
        alt = (normalized_dir / raw.name).resolve()
        if alt.exists():
            return alt
        return raw

    base_candidates = [
        base_dir.resolve(),
        catalog_path.parent.resolve(),
        catalog_path.parent.parent.resolve(),
        results_dir.resolve(),
        normalized_dir.resolve(),
    ]
    for base in base_candidates:
        candidate = (base / raw).resolve()
        if candidate.exists():
            return candidate

    by_name = (normalized_dir / raw.name).resolve()
    if by_name.exists():
        return by_name
    return (catalog_path.parent.resolve() / raw).resolve()


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
        print(f"[series] Aviso: no se pudo forzar run flag para {case_name}.")


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


def _run_and_check(sap_model, case_name: str):
    _set_only_case_to_run(sap_model, case_name)
    ret_run = _ret_code(sap_model.Analyze.RunAnalysis())
    if ret_run != 0:
        raise RuntimeError(f"RunAnalysis fallo para {case_name} (ret={ret_run})")

    case_status, ret = get_case_status_map(sap_model)
    if ret != 0:
        raise RuntimeError(f"GetCaseStatus fallo (ret={ret})")
    if case_name not in case_status:
        raise RuntimeError(f"Caso '{case_name}' no encontrado en GetCaseStatus")
    status = int(case_status[case_name])
    finished = status == 4
    print(f"  Estado {case_name}: {status} (Finished={finished})")
    if not finished:
        raise RuntimeError(f"El caso '{case_name}' no termino correctamente (status={status})")


def main():
    args = _parse_args()
    if args.limit < 1:
        raise ValueError("--limit debe ser >= 1")

    settings_path = Path(args.settings).resolve()
    catalog_path = Path(args.catalog).resolve()
    if not catalog_path.exists():
        raise FileNotFoundError(catalog_path)

    settings_data = _load_settings_data(settings_path)
    settings_root = settings_path.parent.resolve()
    base_dir = settings_path.parent.parent if settings_path.parent.name.lower() == "config" else settings_path.parent

    results_dir = _resolve_path_value(
        settings_data.get("results_dir"),
        base_dir / "results",
        settings_root,
    )
    normalized_dir = _resolve_path_value(
        settings_data.get("normalized_dir"),
        base_dir / "data" / "normalized",
        settings_root,
    )

    (
        _case_name,
        model_path,
        output_time_step,
        _nodes,
        nlth_case_config,
        _overwrite_db,
        output_units,
        accel_in_g,
        _use_ping_pong,
        _ping_pong_cases,
        _use_chain_series,
        _chain_case_prefix,
        _checkpoint_every,
        _clear_results_after_edp,
        initial_gravity_case,
        _energy_link,
        _enable_link_energy,
        _energy_component,
        _energy_point_elm,
        _energy_mode,
    ) = load_nodes_config(str(settings_path))

    catalog = pd.read_csv(catalog_path)
    catalog = catalog.loc[catalog["status_preprocess"] == "OK"].reset_index(drop=True)
    catalog = catalog.head(args.limit)
    if catalog.empty:
        raise RuntimeError("No hay registros OK en el catalogo para ejecutar.")

    sap_model = get_sap2000_model()
    _open_model(sap_model, model_path)
    check_model_loaded_and_unlocked(sap_model, model_path, allow_locked=True)
    set_present_units(sap_model, output_units)
    accel_scale = accel_scale_from_units(output_units, accel_in_g=accel_in_g)

    print(f"[series] Catalogo: {catalog_path}")
    print(f"[series] Registros a ejecutar: {len(catalog.index)}")
    print(f"[series] Prefijo de casos: {args.case_prefix}")
    print(f"[series] Caso inicial de la serie: {initial_gravity_case}")

    previous_case = str(initial_gravity_case).strip()
    for idx, row in catalog.iterrows():
        record_id = str(row["record_id"]).strip()
        case_name = f"{args.case_prefix}_{idx + 1:02d}_{record_id}"
        func_x = f"{case_name}_X"
        func_y = f"{case_name}_Y"

        x_txt = _resolve_record_path(row["x_txt_path"], base_dir, catalog_path, results_dir, normalized_dir)
        y_txt = _resolve_record_path(row["y_txt_path"], base_dir, catalog_path, results_dir, normalized_dir)
        dt = float(row["dt"])
        n_steps = int(row["n_steps"])
        duration = dt * n_steps
        output_steps = max(1, int(round(duration / output_time_step)))

        print(f"[series] [{idx + 1}/{len(catalog.index)}] {record_id}")
        print(f"[series]   Caso nuevo: {case_name}")
        print(f"[series]   Secuencia: {previous_case} -> {case_name}")

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

        inherit_from_case = previous_case if idx > 0 else _case_name
        cloned = False
        if inherit_from_case and not _case_exists(sap_model, case_name):
            cloned = _copy_case_best_effort(sap_model, inherit_from_case, case_name)
        print(f"[series]   Clon: {inherit_from_case} -> {case_name}: {cloned}")

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
            initial_case=previous_case,
            inherit_from_case=inherit_from_case,
        )
        try:
            create_or_update_nlth_case(sap_model, **nlth_kwargs)
        except TypeError:
            nlth_kwargs.pop("initial_case", None)
            nlth_kwargs.pop("p_delta", None)
            nlth_kwargs.pop("inherit_from_case", None)
            create_or_update_nlth_case(sap_model, **nlth_kwargs)

        _run_and_check(sap_model, case_name)
        previous_case = case_name

    print("[series] Serie completada correctamente.")


if __name__ == "__main__":
    main()
