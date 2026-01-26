# main.py

from etabs.connection import EtabsConnection
from config import ETABS_PATH, MODEL_PATH
import logging

# ---------------- Logging ----------------
logging.basicConfig(
    filename="logs/run.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

def main():
    logging.info("=== INICIO FASE 1 ===")

    try:
        etabs = EtabsConnection(
            etabs_path=ETABS_PATH,
            attach=True
        )

        sap_model = etabs.connect()
        logging.info("Conectado a ETABS")

        etabs.open_model(MODEL_PATH)
        logging.info("Modelo abierto correctamente")

        ret = etabs.run_analysis()

        if ret == 0:
            logging.info("Análisis ejecutado correctamente (OK)")
            print("ANÁLISIS OK")
        else:
            logging.warning(f"Análisis terminó con código {ret}")
            print("ANÁLISIS TERMINÓ CON ERRORES")

    except Exception as e:
        logging.exception("Error durante la ejecución")
        print("ERROR:", e)

    logging.info("=== FIN FASE 1 ===")


if __name__ == "__main__":
    main()