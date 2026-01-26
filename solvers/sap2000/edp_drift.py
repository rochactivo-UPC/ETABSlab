import math

import pandas as pd


def compute_consecutive_drifts(df_nodes):
    if df_nodes is None or df_nodes.empty:
        raise ValueError("df_nodes vacio")

    df_sorted = df_nodes.sort_values("z").reset_index(drop=True)
    rows = []

    for idx in range(1, len(df_sorted.index)):
        row_i = df_sorted.iloc[idx]
        row_prev = df_sorted.iloc[idx - 1]
        dz = float(row_i["z"]) - float(row_prev["z"])
        if dz <= 0.0:
            raise RuntimeError(
                f"Delta z invalido entre {row_prev['name']} y {row_i['name']}: {dz}"
            )

        drift_u1 = (float(row_i["u1_max"]) - float(row_prev["u1_max"])) / dz
        drift_u2 = (float(row_i["u2_max"]) - float(row_prev["u2_max"])) / dz
        drift_r = math.hypot(drift_u1, drift_u2)

        rows.append(
            {
                "from_name": row_prev["name"],
                "to_name": row_i["name"],
                "dz": dz,
                "drift_u1": drift_u1,
                "drift_u2": drift_u2,
                "drift_r": drift_r,
            }
        )

    df_drifts = pd.DataFrame(
        rows, columns=["from_name", "to_name", "dz", "drift_u1", "drift_u2", "drift_r"]
    )

    summary = {}
    if not df_drifts.empty:
        idx_u1 = df_drifts["drift_u1"].abs().idxmax()
        idx_u2 = df_drifts["drift_u2"].abs().idxmax()
        idx_r = df_drifts["drift_r"].idxmax()

        summary = {
            "max_drift_u1": float(abs(df_drifts.loc[idx_u1, "drift_u1"])),
            "segment_max_u1": f"{df_drifts.loc[idx_u1, 'from_name']}->{df_drifts.loc[idx_u1, 'to_name']}",
            "max_drift_u2": float(abs(df_drifts.loc[idx_u2, "drift_u2"])),
            "segment_max_u2": f"{df_drifts.loc[idx_u2, 'from_name']}->{df_drifts.loc[idx_u2, 'to_name']}",
            "max_drift_r": float(df_drifts.loc[idx_r, "drift_r"]),
            "segment_max_r": f"{df_drifts.loc[idx_r, 'from_name']}->{df_drifts.loc[idx_r, 'to_name']}",
        }

    return df_drifts, summary
