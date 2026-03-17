from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs.nodes_config import load_nodes_config
from solvers.sap2000.connect import get_sap2000_model
from solvers.sap2000.model_checks import check_model_loaded_and_unlocked
from solvers.sap2000.results_setup import select_case_for_output


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Debug de Results.BaseReact sobre un modelo SAP2000 abierto."
    )
    parser.add_argument(
        "--settings",
        default=str((ROOT / "config" / "settings.yaml").resolve()),
        help="Ruta al settings.yaml",
    )
    parser.add_argument(
        "--case",
        dest="case_name",
        default=None,
        help="Caso a seleccionar para output antes de leer BaseReact.",
    )
    parser.add_argument(
        "--open-model",
        action="store_true",
        help="Abre el modelo indicado en settings antes de consultar resultados.",
    )
    return parser.parse_args()


def _open_model(sap_model, model_path: str):
    model = Path(model_path).resolve()
    if not model.exists():
        raise FileNotFoundError(model)
    ret = sap_model.File.OpenFile(str(model))
    if ret != 0:
        raise RuntimeError(f"No se pudo abrir el modelo SAP2000: {model}")


def _safe_list(x):
    if x is None:
        return []
    if isinstance(x, (list, tuple)):
        return list(x)
    return [x]


def _print_slot(idx: int, value):
    if isinstance(value, (list, tuple)):
        preview = list(value[:5])
        print(
            f"[base-react] slot[{idx}] type={type(value).__name__} "
            f"len={len(value)} preview={preview}"
        )
    else:
        print(f"[base-react] slot[{idx}] type={type(value).__name__} value={value}")


def main():
    args = _parse_args()
    (
        case_name_cfg,
        model_path,
        _output_time_step,
        _nodes,
        _nlth_case_config,
        _overwrite_db,
        _output_units,
        _accel_in_g,
        _use_ping_pong,
        _ping_pong_cases,
        _use_chain_series,
        _chain_case_prefix,
        _checkpoint_every,
        _clear_results_after_edp,
        _initial_gravity_case,
        _energy_link,
        _enable_link_energy,
        _energy_component,
        _energy_point_elm,
        _energy_mode,
    ) = load_nodes_config(args.settings)

    sap_model = get_sap2000_model()
    if args.open_model:
        _open_model(sap_model, model_path)
    check_model_loaded_and_unlocked(sap_model, model_path if args.open_model else None, allow_locked=True)

    target_case = args.case_name or case_name_cfg
    if target_case:
        print(f"[base-react] Seleccionando caso para output: {target_case}")
        select_case_for_output(sap_model, target_case)

    result = sap_model.Results.BaseReact(
        0,
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        0.0,
        0.0,
        0.0,
    )

    print(f"[base-react] raw type={type(result).__name__} len={len(result) if isinstance(result, (list, tuple)) else 'n/a'}")
    print(f"[base-react] raw repr={result!r}")

    if not isinstance(result, (list, tuple)):
        return

    for idx, value in enumerate(result):
        _print_slot(idx, value)

    # Try both common return layouts:
    # Layout A: payload..., ret
    # Layout B: ret, payload...
    if result and isinstance(result[-1], int):
        ret = int(result[-1])
        payload = list(result[:-1])
        layout = "payload..., ret"
    else:
        ret = int(result[0]) if result else 0
        payload = list(result[1:])
        layout = "ret, payload..."

    print(f"[base-react] layout={layout} ret={ret} payload_len={len(payload)}")

    if len(payload) >= 13:
        number_results = payload[0]
        load_case = _safe_list(payload[1])
        step_type = _safe_list(payload[2])
        step_num = _safe_list(payload[3])
        fx = _safe_list(payload[4])
        fy = _safe_list(payload[5])
        fz = _safe_list(payload[6])
        print(f"[base-react] number_results={number_results}")
        print(f"[base-react] load_case[:5]={load_case[:5]}")
        print(f"[base-react] step_type[:5]={step_type[:5]}")
        print(f"[base-react] step_num[:5]={step_num[:5]}")
        print(f"[base-react] fx[:5]={fx[:5]}")
        print(f"[base-react] fy[:5]={fy[:5]}")
        print(f"[base-react] fz[:5]={fz[:5]}")
        if fx:
            print(f"[base-react] maxVx={max(float(x) for x in fx)}")
            print(f"[base-react] minVx={min(float(x) for x in fx)}")
        if fy:
            print(f"[base-react] maxVy={max(float(y) for y in fy)}")
            print(f"[base-react] minVy={min(float(y) for y in fy)}")
    else:
        print("[base-react] payload insuficiente para interpretar la firma documentada.")


if __name__ == "__main__":
    main()
