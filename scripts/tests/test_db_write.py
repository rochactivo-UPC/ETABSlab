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
from solvers.sap2000.edp_drift import compute_consecutive_drifts
from persistence.sqlite_store import (
    init_db,
    insert_run,
    insert_node_disp,
    insert_drifts,
    insert_summary,
)

MODEL_PATH = None
CASE_NAME = None


def main():
    db_path = Path("results").resolve() / "edp.sqlite"
    init_db(db_path)

    config_path = Path("config").resolve() / "settings.yaml"
    case_name, model_path, _output_time_step, nodes, _nlth_case_config = load_nodes_config(config_path)
    target_case = CASE_NAME or case_name
    target_model_path = MODEL_PATH or model_path

    conn = Sap2000Connection()
    sap_model = conn.connect()
    if target_model_path:
        conn.open_model(str(Path(target_model_path).resolve()))

    check_model_loaded_and_unlocked(sap_model, target_model_path, allow_locked=True)
    select_case_for_output(sap_model, target_case)

    df_nodes = get_node_max_displacements(sap_model, nodes)
    df_drifts, summary = compute_consecutive_drifts(df_nodes)

    run_id = insert_run(
        db_path,
        record_id="real-001",
        case_name=target_case,
        dt=None,
        n_steps=None,
        finished=True,
        error="",
    )

    insert_node_disp(db_path, run_id, df_nodes)
    insert_drifts(db_path, run_id, df_drifts)
    insert_summary(db_path, run_id, summary)

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        for table in ["runs", "node_disp", "drifts", "run_summary"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table}: {count}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
