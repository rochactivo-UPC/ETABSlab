from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs.nodes_config import load_nodes_config
from solvers.sap2000.connect import Sap2000Connection
from solvers.sap2000.model_checks import check_model_loaded_and_unlocked
from solvers.sap2000.results_setup import select_case_for_output
from solvers.sap2000.edp_nodes import get_node_max_displacements


MODEL_PATH = None
CASE_NAME = None


def main():
    config_path = Path("config").resolve() / "nodes.yaml"
    case_name, model_path, nodes = load_nodes_config(config_path)
    target_case = CASE_NAME or case_name
    target_model_path = MODEL_PATH or model_path

    conn = Sap2000Connection()
    sap_model = conn.connect()
    if target_model_path:
        conn.open_model(str(Path(target_model_path).resolve()))

    check_model_loaded_and_unlocked(sap_model, target_model_path, allow_locked=True)

    select_case_for_output(sap_model, target_case)
    df = get_node_max_displacements(sap_model, nodes)
    print(df)


if __name__ == "__main__":
    main()
