import pandas as pd
import numpy as np


def _prepare_series(t, u, label):
    if t is None or u is None:
        raise ValueError(f"Serie vacia para {label}")
    t_arr = np.asarray(t, dtype=float)
    u_arr = np.asarray(u, dtype=float)
    if t_arr.size == 0 or u_arr.size == 0:
        raise ValueError(f"Serie vacia para {label}")
    if t_arr.size != u_arr.size:
        raise ValueError(f"Longitudes distintas en {label}: t={t_arr.size}, u={u_arr.size}")
    if t_arr.size > 1 and np.any(np.diff(t_arr) < 0):
        order = np.argsort(t_arr)
        t_arr = t_arr[order]
        u_arr = u_arr[order]
    return t_arr, u_arr


def _align_series(t1, u1, t2, u2):
    if t1.size == t2.size and np.allclose(t1, t2):
        return t1, u1, u2

    t_min = max(float(t1[0]), float(t2[0]))
    t_max = min(float(t1[-1]), float(t2[-1]))
    if t_max <= t_min:
        raise RuntimeError(
            f"Series sin traslape temporal: [{t1[0]}, {t1[-1]}] vs [{t2[0]}, {t2[-1]}]"
        )

    common = np.unique(np.concatenate([t1, t2]))
    common = common[(common >= t_min) & (common <= t_max)]
    if common.size == 0:
        raise RuntimeError("Malla comun vacia para interpolacion")

    u1i = np.interp(common, t1, u1)
    u2i = np.interp(common, t2, u2)
    return common, u1i, u2i


def compute_consecutive_drifts_from_histories(node_histories, return_histories=False):
    if not node_histories:
        raise ValueError("node_histories vacio")

    nodes_sorted = sorted(node_histories, key=lambda n: float(n["z"]))
    rows = []
    histories = []

    for idx in range(1, len(nodes_sorted)):
        node_i = nodes_sorted[idx]
        node_prev = nodes_sorted[idx - 1]
        dz = float(node_i["z"]) - float(node_prev["z"])
        if dz <= 0.0:
            raise RuntimeError(
                f"Delta z invalido entre {node_prev['name']} y {node_i['name']}: {dz}"
            )

        t_i, u1_i = _prepare_series(node_i["t"], node_i["u1"], node_i["name"])
        t_p, u1_p = _prepare_series(node_prev["t"], node_prev["u1"], node_prev["name"])
        _t, u1_i_al, u1_p_al = _align_series(t_i, u1_i, t_p, u1_p)

        t_i, u2_i = _prepare_series(node_i["t"], node_i["u2"], node_i["name"])
        t_p, u2_p = _prepare_series(node_prev["t"], node_prev["u2"], node_prev["name"])
        _t, u2_i_al, u2_p_al = _align_series(t_i, u2_i, t_p, u2_p)

        theta_u1 = (u1_i_al - u1_p_al) / dz
        theta_u2 = (u2_i_al - u2_p_al) / dz
        theta_r = np.hypot(theta_u1, theta_u2)

        drift_u1_max = float(np.max(theta_u1))
        drift_u1_min = float(np.min(theta_u1))
        drift_u2_max = float(np.max(theta_u2))
        drift_u2_min = float(np.min(theta_u2))
        drift_r_max = float(np.max(theta_r))
        drift_r_min = float(np.min(theta_r))

        drift_u1 = float(np.max(np.abs(theta_u1)))
        drift_u2 = float(np.max(np.abs(theta_u2)))
        drift_r = drift_r_max

        rows.append(
            {
                "from_name": node_prev["name"],
                "to_name": node_i["name"],
                "dz": dz,
                "drift_u1_max": drift_u1_max,
                "drift_u1_min": drift_u1_min,
                "drift_u2_max": drift_u2_max,
                "drift_u2_min": drift_u2_min,
                "drift_r_max": drift_r_max,
                "drift_r_min": drift_r_min,
                "drift_u1": drift_u1,
                "drift_u2": drift_u2,
                "drift_r": drift_r,
            }
        )
        if return_histories:
            histories.append(
                {
                    "from_name": node_prev["name"],
                    "to_name": node_i["name"],
                    "dz": dz,
                    "t": list(_t),
                    "theta_u1": list(theta_u1),
                    "theta_u2": list(theta_u2),
                    "theta_r": list(theta_r),
                }
            )

    df_drifts = pd.DataFrame(
        rows,
        columns=[
            "from_name",
            "to_name",
            "dz",
            "drift_u1_max",
            "drift_u1_min",
            "drift_u2_max",
            "drift_u2_min",
            "drift_r_max",
            "drift_r_min",
            "drift_u1",
            "drift_u2",
            "drift_r",
        ],
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


def compute_consecutive_drifts(df_nodes=None, node_histories=None, return_histories=False):
    if node_histories is None:
        raise ValueError(
            "compute_consecutive_drifts requiere node_histories (historia temporal)."
        )
    return compute_consecutive_drifts_from_histories(
        node_histories, return_histories=return_histories
    )
