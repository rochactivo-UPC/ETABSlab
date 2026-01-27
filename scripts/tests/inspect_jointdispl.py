from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs.nodes_config import load_nodes_config
from solvers.sap2000.connect import Sap2000Connection
from solvers.sap2000.model_checks import check_model_loaded_and_unlocked
from solvers.sap2000.results_setup import select_case_for_output


MODEL_PATH = None
CASE_NAME = None
JOINT_NAME = None


def _length(value):
    try:
        return len(value)
    except TypeError:
        return None


def main():
    config_path = Path("config").resolve() / "settings.yaml"
    case_name, model_path, _output_time_step, nodes, _nlth_case_config = load_nodes_config(config_path)

    target_case = CASE_NAME or case_name
    target_joint = JOINT_NAME or nodes[0].joint
    target_model_path = MODEL_PATH or model_path

    conn = Sap2000Connection()
    sap_model = conn.connect()
    if target_model_path:
        conn.open_model(str(Path(target_model_path).resolve()))

    check_model_loaded_and_unlocked(sap_model, target_model_path, allow_locked=True)

    select_case_for_output(sap_model, target_case)

    result = sap_model.Results.JointDispl(
        target_joint,
        0,
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
        [],
        [],
    )

    if not isinstance(result, (tuple, list)) or len(result) < 9:
        print(f"Respuesta JointDispl inesperada: {result}")
        if isinstance(result, (tuple, list)):
            print(f"Len respuesta: {len(result)}")
            for idx, item in enumerate(result):
                print(f"[{idx}] type={type(item)} value={item}")
        return

    ret = result[0]
    number_results = result[1] if len(result) > 1 else None
    obj = result[2] if len(result) > 2 else None
    elm = result[3] if len(result) > 3 else None
    load_case = result[4] if len(result) > 4 else None
    step_type = result[5] if len(result) > 5 else None
    step_num = result[6] if len(result) > 6 else None
    u1 = result[7] if len(result) > 7 else None
    u2 = result[8] if len(result) > 8 else None

    print(f"Joint usado: {target_joint}")
    print(f"ret: {ret}")
    print(f"NumberResults: {number_results}")
    print(f"Len respuesta: {len(result)}")
    for idx, item in enumerate(result):
        if idx > 12:
            break
        print(f"[{idx}] type={type(item)} value={item}")
    print(f"Obj: type={type(obj)} len={_length(obj)}")
    print(f"Elm: type={type(elm)} len={_length(elm)}")
    print(f"LoadCase: type={type(load_case)} len={_length(load_case)}")
    print(f"StepType: type={type(step_type)} len={_length(step_type)}")
    print(f"StepNum: type={type(step_num)} len={_length(step_num)}")
    print(f"U1: type={type(u1)} len={_length(u1)}")
    print(f"U2: type={type(u2)} len={_length(u2)}")

    if isinstance(number_results, tuple) and len(number_results) == 0:
        print("NumberResults vacio. Posibles causas:")
        print("- El caso no tiene resultados (no se corrio).")
        print("- El caso seleccionado para output no coincide.")
        print("- El joint no pertenece al modelo o no tiene DOF.")


if __name__ == "__main__":
    main()
