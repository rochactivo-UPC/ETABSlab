from pathlib import Path

from solvers.sap2000.connect import get_sap2000_model
from batch.run_batch_from_catalog import run_batch_from_catalog

MODEL_PATH = r"C:\Users\rocha\Desktop\SAP2000 test\test.sdb"


def _open_model(sap_model, model_path: str):
    model_path = Path(model_path).resolve()
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    ret = sap_model.File.OpenFile(str(model_path))
    if ret != 0:
        raise RuntimeError(f"No se pudo abrir el modelo SAP2000: {model_path}")


def main():
    sap_model = get_sap2000_model()
    _open_model(sap_model, MODEL_PATH)

    catalog_csv = Path("results").resolve() / "catalog.csv"
    run_batch_from_catalog(
        sap_model,
        catalog_csv,
        case_name="NLTH_BATCH",
        overwrite_functions=True,
        resume=True
    )


if __name__ == "__main__":
    main()
