from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs.nodes_config import load_nodes_config
from solvers.sap2000.connect import get_sap2000_model
from solvers.sap2000.model_checks import check_model_loaded_and_unlocked
from batch.run_batch_from_catalog import run_batch_from_catalog

MODEL_PATH = None
CASE_NAME = None


def _open_model(sap_model, model_path: str):
    model_path = Path(model_path).resolve()
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    ret = sap_model.File.OpenFile(str(model_path))
    if ret != 0:
        raise RuntimeError(f"No se pudo abrir el modelo SAP2000: {model_path}")


def main():
    config_path = Path("config").resolve() / "nodes.yaml"
    case_name, model_path, _nodes = load_nodes_config(config_path)
    target_case = CASE_NAME or case_name
    target_model_path = MODEL_PATH or model_path

    sap_model = get_sap2000_model()
    if target_model_path:
        _open_model(sap_model, target_model_path)
    check_model_loaded_and_unlocked(sap_model, target_model_path, allow_locked=True)

    catalog_csv = Path("results").resolve() / "catalog.csv"
    run_batch_from_catalog(
        sap_model,
        catalog_csv,
        case_name=target_case,
        overwrite_functions=True,
        resume=True
    )


if __name__ == "__main__":
    main()
