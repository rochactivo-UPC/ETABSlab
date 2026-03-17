from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs.nodes_config import load_nodes_config
from solvers.sap2000.connect import get_sap2000_model
from solvers.sap2000.analysis import get_case_status_map
from solvers.sap2000.model_checks import check_model_loaded_and_unlocked


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
            "Prueba cadena por copias: A -> A1 -> A2 -> ... -> An. "
            "Cada caso nuevo inicia desde el caso anterior."
        )
    )
    parser.add_argument(
        "--settings",
        default=str((ROOT / "config" / "settings.yaml").resolve()),
        help="Ruta al settings.yaml",
    )
    parser.add_argument(
        "--seed-case",
        default="",
        help="Caso semilla (por defecto usa ping_pong_cases[0], p.ej. NLTH_A).",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=5,
        help="Numero total de analisis de la cadena (incluye seed-case).",
    )
    parser.add_argument(
        "--delete-analysis-results",
        action="store_true",
        help=(
            "Si se activa, llama Analyze.DeleteAnalysisResults despues de cada corrida. "
            "Nota: puede romper la cadena de initial conditions."
        ),
    )
    return parser.parse_args()


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
    # Best effort: disable all known cases first.
    try:
        _n, names, _status, ret = sap_model.Analyze.GetCaseStatus()
        if ret == 0 and isinstance(names, (list, tuple)):
            for name in names:
                _set_run_case_flag(sap_model, str(name), False)
    except Exception:
        pass
    if not _set_run_case_flag(sap_model, case_name, True):
        print(f"[chain-clone] Aviso: no se pudo forzar run flag para {case_name}.")


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


def _set_initial_case(sap_model, case_name: str, initial_case: str):
    method = getattr(sap_model.LoadCases.DirHistNonlinear, "SetInitialCase", None)
    if method is None:
        raise RuntimeError("Metodo SetInitialCase no disponible en SAP2000")
    ret = _ret_code(method(case_name, str(initial_case)))
    if ret != 0:
        raise RuntimeError(
            f"No se pudo configurar initial case de '{case_name}' a '{initial_case}' (ret={ret})"
        )


def _copy_case(sap_model, source_case: str, target_case: str):
    # Try common API names/signatures for case copy.
    load_cases = sap_model.LoadCases
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
            ret = _ret_code(method(*args))
            if ret == 0:
                return
        except Exception:
            continue
    raise RuntimeError(
        "No se encontro un metodo compatible para copiar casos (LoadCases.Copy/CopyCase/Duplicate)."
    )


def _delete_case(sap_model, case_name: str):
    method = getattr(sap_model.LoadCases, "Delete", None)
    if method is None:
        print(f"[chain-clone] Aviso: LoadCases.Delete no disponible; no se elimina {case_name}.")
        return
    try:
        ret = _ret_code(method(case_name))
        if ret != 0:
            print(f"[chain-clone] Aviso: no se pudo eliminar caso {case_name} (ret={ret}).")
    except Exception as exc:
        print(f"[chain-clone] Aviso: error eliminando {case_name}: {exc}")


def _delete_analysis_results(sap_model):
    method = getattr(sap_model.Analyze, "DeleteAnalysisResults", None)
    if method is None:
        print("[chain-clone] Aviso: Analyze.DeleteAnalysisResults no disponible.")
        return
    try:
        ret = _ret_code(method())
        print(f"[chain-clone] DeleteAnalysisResults ret={ret}")
    except Exception as exc:
        print(f"[chain-clone] Aviso: error en DeleteAnalysisResults: {exc}")


def main():
    args = _parse_args()
    if args.n < 1:
        raise ValueError("--n debe ser >= 1")

    (
        _case_name,
        model_path,
        _output_time_step,
        _nodes,
        _nlth_case_config,
        _overwrite_db,
        _output_units,
        _accel_in_g,
        _use_ping_pong,
        ping_pong_cases,
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
    ) = load_nodes_config(args.settings)

    seed_case = str(args.seed_case).strip() or str(ping_pong_cases[0]).strip()
    if not seed_case:
        raise ValueError("No se pudo resolver seed-case.")

    sap_model = get_sap2000_model()
    _open_model(sap_model, model_path)
    check_model_loaded_and_unlocked(sap_model, model_path, allow_locked=True)

    print(f"[chain-clone] Step 1/{args.n}: ejecutando caso semilla {seed_case}")
    print(f"[chain-clone] Recomendado: {seed_case} debe partir de {initial_gravity_case} en SAP.")
    _run_and_check(sap_model, seed_case)

    prev_case = seed_case
    for i in range(2, args.n + 1):
        new_case = f"{seed_case}{i-1}"
        print(f"[chain-clone] Step {i}/{args.n}: copiando {prev_case} -> {new_case}")
        _copy_case(sap_model, prev_case, new_case)
        print(f"[chain-clone] Step {i}/{args.n}: configurando {new_case} <- {prev_case}")
        _set_initial_case(sap_model, new_case, prev_case)
        _run_and_check(sap_model, new_case)

        if args.delete_analysis_results:
            _delete_analysis_results(sap_model)

        old_case = prev_case
        prev_case = new_case
        _delete_case(sap_model, old_case)

    print("[chain-clone] Cadena completada correctamente.")


if __name__ == "__main__":
    main()
