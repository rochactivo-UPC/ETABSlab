from datetime import datetime
from pathlib import Path
import sqlite3


def _connect(db_path):
    db_path = Path(db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))


def init_db(db_path):
    conn = _connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT,
                case_name TEXT,
                dt REAL,
                n_steps INTEGER,
                finished INTEGER,
                created_at TEXT,
                error TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS node_disp (
                run_id INTEGER,
                name TEXT,
                joint TEXT,
                z REAL,
                u1_max REAL,
                u2_max REAL,
                r_max REAL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS drifts (
                run_id INTEGER,
                from_name TEXT,
                to_name TEXT,
                dz REAL,
                drift_u1 REAL,
                drift_u2 REAL,
                drift_r REAL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS run_summary (
                run_id INTEGER,
                max_drift_u1 REAL,
                seg_max_u1 TEXT,
                max_drift_u2 REAL,
                seg_max_u2 TEXT,
                max_drift_r REAL,
                seg_max_r TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def insert_run(db_path, record_id, case_name, dt, n_steps, finished, error=""):
    conn = _connect(db_path)
    try:
        cursor = conn.cursor()
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        cursor.execute(
            """
            INSERT INTO runs (
                record_id, case_name, dt, n_steps, finished, created_at, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(record_id),
                str(case_name),
                dt,
                n_steps,
                int(bool(finished)),
                created_at,
                str(error or ""),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def insert_node_disp(db_path, run_id, df_nodes):
    if df_nodes is None or df_nodes.empty:
        return
    conn = _connect(db_path)
    try:
        cursor = conn.cursor()
        rows = []
        for row in df_nodes.itertuples(index=False):
            r_max = getattr(row, "r_max", None)
            rows.append(
                (
                    run_id,
                    row.name,
                    row.joint,
                    float(row.z),
                    float(row.u1_max),
                    float(row.u2_max),
                    float(r_max) if r_max is not None else None,
                )
            )
        cursor.executemany(
            """
            INSERT INTO node_disp (
                run_id, name, joint, z, u1_max, u2_max, r_max
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def insert_drifts(db_path, run_id, df_drifts):
    if df_drifts is None or df_drifts.empty:
        return
    conn = _connect(db_path)
    try:
        cursor = conn.cursor()
        rows = [
            (
                run_id,
                row.from_name,
                row.to_name,
                float(row.dz),
                float(row.drift_u1),
                float(row.drift_u2),
                float(row.drift_r),
            )
            for row in df_drifts.itertuples(index=False)
        ]
        cursor.executemany(
            """
            INSERT INTO drifts (
                run_id, from_name, to_name, dz, drift_u1, drift_u2, drift_r
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def insert_summary(db_path, run_id, summary):
    if not summary:
        return
    conn = _connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO run_summary (
                run_id, max_drift_u1, seg_max_u1,
                max_drift_u2, seg_max_u2,
                max_drift_r, seg_max_r
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                summary.get("max_drift_u1"),
                summary.get("segment_max_u1"),
                summary.get("max_drift_u2"),
                summary.get("segment_max_u2"),
                summary.get("max_drift_r"),
                summary.get("segment_max_r"),
            ),
        )
        conn.commit()
    finally:
        conn.close()
