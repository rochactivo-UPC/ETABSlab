from pathlib import Path
import sys

import pandas as pd
import matplotlib.pyplot as plt
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DB_PATH = None
RUN_ID = None


def _get_db_path():
    if DB_PATH:
        return Path(DB_PATH).resolve()
    return Path("results").resolve() / "edp.sqlite"


def _load_table(conn, table, run_id=None):
    if run_id is None:
        return pd.read_sql_query(f"SELECT * FROM {table}", conn)
    return pd.read_sql_query(
        f"SELECT * FROM {table} WHERE run_id = ?", conn, params=(run_id,)
    )


def _get_latest_run_id(conn):
    row = conn.execute("SELECT MAX(run_id) FROM runs").fetchone()
    return row[0] if row else None


def _print_counts(conn):
    for table in ["runs", "node_disp", "drifts", "run_summary"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count}")


def _plot_node_disp(df_nodes):
    if df_nodes.empty:
        print("No hay node_disp para graficar.")
        return
    df_nodes = df_nodes.sort_values(["run_id", "z"])
    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(10, 4), sharey=True)
    ax_x, ax_y = axes
    for run_id, group in df_nodes.groupby("run_id"):
        ax_x.plot(
            group["u1_max"],
            group["z"],
            marker="o",
            label=f"run {run_id}",
        )
        ax_y.plot(
            group["u2_max"],
            group["z"],
            marker="o",
            label=f"run {run_id}",
        )
    ax_x.set_xlabel("U1 max (X)")
    ax_y.set_xlabel("U2 max (Y)")
    ax_x.set_ylabel("z")
    ax_x.set_title("Desplazamientos X (U1)")
    ax_y.set_title("Desplazamientos Y (U2)")
    ax_x.grid(True, linestyle="--", alpha=0.4)
    ax_y.grid(True, linestyle="--", alpha=0.4)
    ax_x.legend()


def _plot_drifts(df_drifts):
    if df_drifts.empty:
        print("No hay drifts para graficar.")
        return
    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(10, 4), sharey=True)
    ax_x, ax_y = axes
    df_drifts = df_drifts.sort_values(["run_id"])
    for run_id, group in df_drifts.groupby("run_id"):
        y = range(len(group.index))
        ax_x.plot(group["drift_u1"], y, marker="o", label=f"run {run_id}")
        ax_y.plot(group["drift_u2"], y, marker="o", label=f"run {run_id}")
    ax_x.set_xlabel("Drift U1 (X)")
    ax_y.set_xlabel("Drift U2 (Y)")
    ax_x.set_ylabel("Segmento (orden z)")
    ax_x.set_title("Drifts X (U1)")
    ax_y.set_title("Drifts Y (U2)")
    ax_x.grid(True, linestyle="--", alpha=0.4)
    ax_y.grid(True, linestyle="--", alpha=0.4)
    ax_x.legend()


def main():
    db_path = _get_db_path()
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    with sqlite3.connect(str(db_path)) as conn:
        _print_counts(conn)

        run_id = RUN_ID or _get_latest_run_id(conn)
        if run_id is None:
            print("No hay runs en la base.")
            return

        if RUN_ID is None:
            df_nodes = _load_table(conn, "node_disp")
            df_drifts = _load_table(conn, "drifts")
            df_summary = _load_table(conn, "run_summary")
        else:
            df_nodes = _load_table(conn, "node_disp", run_id=run_id)
            df_drifts = _load_table(conn, "drifts", run_id=run_id)
            df_summary = _load_table(conn, "run_summary", run_id=run_id)

        print(df_nodes)
        print(df_drifts)
        print(df_summary)

        _plot_node_disp(df_nodes)
        _plot_drifts(df_drifts)
        plt.show()


if __name__ == "__main__":
    main()
