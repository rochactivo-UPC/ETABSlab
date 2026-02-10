from pathlib import Path
import logging
import traceback
import sys
import sys
import argparse

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


def _parse_args():
    parser = argparse.ArgumentParser(description="Ejecuta batch NLTH desde catalogo")
    parser.add_argument(
        "--catalog",
        dest="catalog",
        default=None,
        help="Ruta al catalogo CSV a ejecutar",
    )
    parser.add_argument(
        "--settings",
        dest="settings",
        default=None,
        help="Ruta al settings.yaml",
    )
    return parser.parse_args()


def main():
    args = _parse_args()
    if args.settings:
        config_path = Path(args.settings).resolve()
        base_dir = config_path.parent.parent
    elif getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
        config_path = (base_dir / "config" / "settings.yaml").resolve()
    else:
        base_dir = Path(__file__).resolve().parents[1]
        config_path = (base_dir / "config" / "settings.yaml").resolve()

    logs_dir = (base_dir / "logs").resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "run_nlth_batch.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logging.info("Iniciando run_nlth_batch")
    (
        case_name,
        model_path,
        _output_time_step,
        _nodes,
        _nlth_case_config,
        _overwrite_db,
        _output_units,
        _accel_in_g,
        _use_ping_pong,
        _ping_pong_cases,
        _checkpoint_every,
        _clear_results_after_edp,
        _initial_gravity_case,
        _energy_link,
        _enable_link_energy,
        _energy_component,
        _energy_point_elm,
        _energy_mode,
    ) = load_nodes_config(config_path)
    target_case = CASE_NAME or case_name
    target_model_path = MODEL_PATH or model_path

    sap_model = get_sap2000_model()
    if target_model_path:
        _open_model(sap_model, target_model_path)
    check_model_loaded_and_unlocked(sap_model, target_model_path, allow_locked=True)

    if args.catalog:
        catalog_csv = Path(args.catalog).resolve()
        logging.info(f"Usando catalogo indicado por argumento: {catalog_csv}")
    else:
        test_catalog = (base_dir / "results" / "catalog_test2.csv").resolve()
        if test_catalog.exists():
            logging.info(f"Usando catalogo de prueba: {test_catalog}")
            catalog_csv = test_catalog
        else:
            catalog_csv = (base_dir / "results" / "catalog.csv").resolve()
    try:
        run_batch_from_catalog(
            sap_model,
            catalog_csv,
            case_name=target_case,
            overwrite_functions=True,
            resume=False,
            overwrite_results=True,
            base_dir=base_dir,
            settings_path=config_path,
        )
        logging.info("Batch finalizado correctamente")
    except Exception:
        logging.error("Error en ejecución del batch")
        logging.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
