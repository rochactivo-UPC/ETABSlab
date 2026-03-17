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
            "Prueba secuencia ping-pong sin postproceso: "
            "Inicial (desde cero) -> A (desde Inicial) -> B (desde A) -> A (desde B) ..."
        )
    )
    parser.add_argument(
        "--settings",
        default=str((ROOT / "config" / "settings.yaml").resolve()),
        help="Ruta al settings.yaml",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=4,
        help="Cantidad de pasos de secuencia despues del caso inicial (>=1).",
    )
    parser.add_argument(
        "--third-case",
        default="",
        help="Nombre de un tercer caso NLTH (ej. NLTH_C) para secuencia A-B-C.",
    )
    parser.add_argument(
        "--cases",
        default="",
        help="Lista explicita de casos separados por coma. Ej: NLTH_A,NLTH_B,NLTH_C",
    )
    return parser.parse_args()


def _set_initial_case(sap_model, case_name: str, initial_case: str | None):
    method = getattr(sap_model.LoadCases.DirHistNonlinear, "SetInitialCase", None)
    if method is None:
        raise RuntimeError("Metodo SetInitialCase no disponible en SAP2000")
    init_name = "" if not initial_case else str(initial_case).strip()
    ret = method(case_name, init_name)
    if ret != 0:
        raise RuntimeError(
            f"No se pudo configurar initial case de '{case_name}' a '{init_name}' (ret={ret})"
        )


def _run_and_check(sap_model, target_case: str):
    ret_run = sap_model.Analyze.RunAnalysis()
    if ret_run != 0:
        raise RuntimeError(f"RunAnalysis fallo (ret={ret_run})")

    case_status, ret = get_case_status_map(sap_model)
    if ret != 0:
        raise RuntimeError(f"GetCaseStatus fallo (ret={ret})")
    if target_case not in case_status:
        raise RuntimeError(f"Caso '{target_case}' no encontrado en GetCaseStatus")

    status = int(case_status[target_case])
    finished = status == 4
    print(f"  Estado {target_case}: {status} (Finished={finished})")
    if not finished:
        raise RuntimeError(f"El caso '{target_case}' no termino correctamente (status={status})")


def main():
    args = _parse_args()
    if args.steps < 1:
        raise ValueError("--steps debe ser >= 1")

    (
        _case_name,
        model_path,
        _output_time_step,
        _nodes,
        _nlth_case_config,
        _overwrite_db,
        _output_units,
        _accel_in_g,
        use_ping_pong,
        ping_pong_cases,
        _use_chain_series,
        _chain_case_prefix,
        _checkpoint_every,
        clear_results_after_edp,
        initial_gravity_case,
        _energy_link,
        _enable_link_energy,
        _energy_component,
        _energy_point_elm,
        _energy_mode,
    ) = load_nodes_config(args.settings)

    if clear_results_after_edp:
        print(
            "[seq-check] Aviso: settings tiene clear_results_after_edp=True. "
            "Esta prueba no borra resultados, pero deja ese campo en False para el flujo batch."
        )
    if not use_ping_pong:
        print("[seq-check] Aviso: use_ping_pong=False en settings, pero la prueba forzara secuencia A/B.")

    case_a = str(ping_pong_cases[0]).strip()
    case_b = str(ping_pong_cases[1]).strip()
    case_init = str(initial_gravity_case).strip()
    if not case_a or not case_b or not case_init:
        raise ValueError("Casos invalidos en settings: ping_pong_cases o initial_gravity_case vacios")

    if args.cases.strip():
        sequence_cases = [x.strip() for x in args.cases.split(",") if x.strip()]
    else:
        sequence_cases = [case_a, case_b]
        third = str(args.third_case).strip()
        if third:
            sequence_cases.append(third)
    if len(sequence_cases) < 2:
        raise ValueError("Debes definir al menos 2 casos en secuencia.")
    print(f"[seq-check] Secuencia configurada: {' -> '.join(sequence_cases)}")

    sap_model = get_sap2000_model()
    _open_model(sap_model, model_path)
    check_model_loaded_and_unlocked(sap_model, model_path, allow_locked=True)

    print("[seq-check] Paso 0: caso inicial (tal como esta configurado en SAP)")
    print(f"[seq-check] Ejecutando {case_init}")
    _run_and_check(sap_model, case_init)

    prev = case_init
    for i in range(args.steps):
        target = sequence_cases[i % len(sequence_cases)]
        print(f"[seq-check] Paso {i + 1}: configurando {target} <- {prev}")
        _set_initial_case(sap_model, target, prev)
        _run_and_check(sap_model, target)
        prev = target

    print("[seq-check] Secuencia completada correctamente.")


if __name__ == "__main__":
    main()
