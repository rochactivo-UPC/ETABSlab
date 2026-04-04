from pathlib import Path
import sys
import argparse
import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs.nodes_config import load_nodes_config
from solvers.sap2000.units import infer_force_unit_label, infer_length_unit_label

DEFAULT_RESULTS_DIRS = [
    Path(r"C:\Users\rocha\Desktop\test_Fran\results_complete_model\rand"),
    Path(r"C:\Users\rocha\Desktop\test_Fran\results_complete_model\asc"),
    Path(r"C:\Users\rocha\Desktop\test_Fran\results_complete_model\des"),
]
DEFAULT_LABELS = ["rand", "asc", "des"]
DB_COLORS = {
    "rand": "#4C78A8FF",
    "asc": "#F51818",
    "des": "#54A24B",
}
MARKERS = {
    ("X", "max"): "o",
    ("X", "min"): "x",
    ("Y", "max"): "^",
    ("Y", "min"): "s",
}
LINESTYLES = {
    ("X", "max"): "-",
    ("X", "min"): "--",
    ("Y", "max"): "-.",
    ("Y", "min"): ":",
}
RUN_WIDTH = 0.5
MEAN_WIDTH = 2.5


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Compare multiple ETABSlab edp.sqlite databases in a single set of plots."
    )
    parser.add_argument(
        "--results-dir",
        dest="results_dirs",
        action="append",
        default=None,
        help="Results directory containing edp.sqlite. Repeat for multiple databases.",
    )
    parser.add_argument(
        "--label",
        dest="labels",
        action="append",
        default=None,
        help="Display label for the previous/parallel results-dir. Repeat in the same order.",
    )
    parser.add_argument(
        "--export-dir",
        dest="export_dir",
        default=None,
        help="Directory to export PNG/PDF figures and CSV summaries.",
    )
    parser.add_argument(
        "--settings",
        dest="settings_path",
        default=None,
        help="Optional settings.yaml used to infer output units.",
    )
    parser.add_argument(
        "--hide-titles",
        dest="hide_titles",
        action="store_true",
        help="Hide plot titles.",
    )
    parser.add_argument(
        "--hide-trend-lines",
        dest="hide_trend_lines",
        action="store_true",
        help="Do not draw trend lines in the base shear vs displacement plot.",
    )
    parser.add_argument(
        "--quadratic-trend",
        dest="quadratic_trend",
        action="store_true",
        help="Use a quadratic trend instead of a linear trend in the base shear vs displacement plot.",
    )
    parser.add_argument(
        "--quadratic-through-origin",
        dest="quadratic_through_origin",
        action="store_true",
        help="When using --quadratic-trend, constrain the quadratic fit to pass through the origin.",
    )
    return parser.parse_args()


def _guess_settings_path(explicit: str | None, results_dirs: list[Path]) -> Path | None:
    if explicit:
        path = Path(explicit).resolve()
        return path if path.exists() else None
    candidates = []
    for results_dir in results_dirs:
        candidates.extend(
            [
                (results_dir / "settings.yaml").resolve(),
                (results_dir / "config" / "settings.yaml").resolve(),
                (results_dir.parent / "settings.yaml").resolve(),
                (results_dir.parent / "config" / "settings.yaml").resolve(),
            ]
        )
    candidates.append((ROOT / "config" / "settings.yaml").resolve())
    for path in candidates:
        if path.exists():
            return path
    return None


def _resolve_units(settings_path: Path | None):
    if settings_path is None:
        return "cm", "force units"
    try:
        (
            _case_name,
            _model_path,
            _output_time_step,
            _nodes,
            _nlth_case_config,
            _overwrite_db,
            output_units,
            _accel_in_g,
            *_rest,
        ) = load_nodes_config(str(settings_path))
    except Exception:
        return "cm", "force units"
    return (
        infer_length_unit_label(output_units) or "cm",
        infer_force_unit_label(output_units) or "force units",
    )


def _style_axis(ax, xlabel: str, title: str, show_titles: bool):
    ax.set_xlabel(xlabel)
    if show_titles:
        ax.set_title(title)
    ax.grid(True, linestyle="--", alpha=0.2, linewidth=0.6)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=5))


def _set_limits_from_values(ax, values, axis="x", symmetric=False, positive_y=False):
    series = pd.Series(list(values)).dropna()
    if series.empty:
        return
    if symmetric:
        limit = float(series.abs().max())
        if limit <= 0.0:
            limit = 1.0
        pad = 0.05 * limit
        lo, hi = -(limit + pad), limit + pad
    elif positive_y:
        hi = float(series.max())
        if hi <= 0.0:
            hi = 1.0
        lo = 0.0
    else:
        lo = float(series.min())
        hi = float(series.max())
        span = max(abs(lo), abs(hi), 1.0)
        pad = 0.05 * span
        lo -= pad
        hi += pad
    if axis == "x":
        ax.set_xlim(lo, hi)
    else:
        ax.set_ylim(lo, hi)


def _load_db_bundle(results_dir: Path, label: str):
    db_path = (results_dir / "edp.sqlite").resolve()
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        runs = pd.read_sql_query("SELECT * FROM runs", conn)
        node_disp = pd.read_sql_query("SELECT * FROM node_disp", conn)
        drifts = pd.read_sql_query("SELECT * FROM drifts", conn)
        run_summary = pd.read_sql_query("SELECT * FROM run_summary", conn)
    for df in [runs, node_disp, drifts, run_summary]:
        if not df.empty:
            df["db_label"] = label
    return {
        "label": label,
        "results_dir": results_dir,
        "runs": runs,
        "node_disp": node_disp,
        "drifts": drifts,
        "run_summary": run_summary,
    }


def _plot_displacement(bundles, length_unit: str, show_titles: bool):
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    ax_x, ax_y = axes
    all_x = []
    all_y = []
    all_z = []

    for bundle in bundles:
        df = bundle["node_disp"]
        if df.empty:
            continue
        color = DB_COLORS.get(bundle["label"], None)
        df = df.sort_values(["run_id", "z"])
        for _, group in df.groupby("run_id"):
            ax_x.plot(group["u1_max"], group["z"], color=color, linewidth=RUN_WIDTH, alpha=0.2)
            ax_x.plot(group["u1_min"], group["z"], color=color, linewidth=RUN_WIDTH, alpha=0.2, linestyle="--")
            ax_y.plot(group["u2_max"], group["z"], color=color, linewidth=RUN_WIDTH, alpha=0.2)
            ax_y.plot(group["u2_min"], group["z"], color=color, linewidth=RUN_WIDTH, alpha=0.2, linestyle="--")
        mean_df = (
            df.groupby("z", as_index=False)[["u1_max", "u1_min", "u2_max", "u2_min"]]
            .mean()
            .sort_values("z")
        )
        ax_x.plot(mean_df["u1_max"], mean_df["z"], color=color, linewidth=MEAN_WIDTH, label=f"{bundle['label']} max mean")
        ax_x.plot(mean_df["u1_min"], mean_df["z"], color=color, linewidth=MEAN_WIDTH, linestyle="--", label=f"{bundle['label']} min mean")
        ax_y.plot(mean_df["u2_max"], mean_df["z"], color=color, linewidth=MEAN_WIDTH, label=f"{bundle['label']} max mean")
        ax_y.plot(mean_df["u2_min"], mean_df["z"], color=color, linewidth=MEAN_WIDTH, linestyle="--", label=f"{bundle['label']} min mean")
        all_x.extend(df["u1_max"].tolist())
        all_x.extend(df["u1_min"].tolist())
        all_y.extend(df["u2_max"].tolist())
        all_y.extend(df["u2_min"].tolist())
        all_z.extend(df["z"].tolist())

    ax_x.set_ylabel(f"Height ({length_unit})")
    ax_y.set_ylabel(f"Height ({length_unit})")
    _style_axis(ax_x, f"U1 Displacement ({length_unit})", "Displacement Profile - X", show_titles)
    _style_axis(ax_y, f"U2 Displacement ({length_unit})", "Displacement Profile - Y", show_titles)
    _set_limits_from_values(ax_x, all_x, axis="x")
    _set_limits_from_values(ax_y, all_y, axis="x")
    _set_limits_from_values(ax_x, all_z, axis="y", positive_y=True)
    _set_limits_from_values(ax_y, all_z, axis="y", positive_y=True)
    ax_x.legend(fontsize=8)
    ax_y.legend(fontsize=8)
    fig.tight_layout()
    return fig


def _build_step_coords(group: pd.DataFrame, max_col: str, min_col: str):
    ordered = group.reset_index(drop=True)
    h = 0.0
    out = {"x_max": [0.0], "x_min": [0.0], "y": [0.0]}
    for row in ordered.itertuples(index=False):
        z0 = h
        z1 = h + float(row.dz)
        out["x_max"].extend([float(getattr(row, max_col)), float(getattr(row, max_col))])
        out["x_min"].extend([float(getattr(row, min_col)), float(getattr(row, min_col))])
        out["y"].extend([z0, z1])
        h = z1
    return out


def _build_story_table(group: pd.DataFrame) -> pd.DataFrame:
    ordered = group.reset_index(drop=True)
    rows = []
    z_bottom = 0.0
    for story_idx, row in enumerate(ordered.itertuples(index=False)):
        dz = float(row.dz)
        z_top = z_bottom + dz
        rows.append(
            {
                "story_idx": story_idx,
                "z_bottom": z_bottom,
                "z_top": z_top,
                "drift_u1_max": float(row.drift_u1_max),
                "drift_u1_min": float(row.drift_u1_min),
                "drift_u2_max": float(row.drift_u2_max),
                "drift_u2_min": float(row.drift_u2_min),
            }
        )
        z_bottom = z_top
    return pd.DataFrame(rows)


def _plot_drift(bundles, length_unit: str, show_titles: bool):
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    ax_x, ax_y = axes
    all_dx = []
    all_dy = []
    all_z = []

    for bundle in bundles:
        df = bundle["drifts"]
        if df.empty:
            continue
        color = DB_COLORS.get(bundle["label"], None)
        df = df.sort_values(["run_id"])
        per_story_max = []
        per_story_min = []
        for _, group in df.groupby("run_id"):
            coords_x = _build_step_coords(group, "drift_u1_max", "drift_u1_min")
            coords_y = _build_step_coords(group, "drift_u2_max", "drift_u2_min")
            ax_x.plot(coords_x["x_max"], coords_x["y"], color=color, linewidth=RUN_WIDTH, alpha=0.2)
            ax_x.plot(coords_x["x_min"], coords_x["y"], color=color, linewidth=RUN_WIDTH, alpha=0.2, linestyle="--")
            ax_y.plot(coords_y["x_max"], coords_y["y"], color=color, linewidth=RUN_WIDTH, alpha=0.2)
            ax_y.plot(coords_y["x_min"], coords_y["y"], color=color, linewidth=RUN_WIDTH, alpha=0.2, linestyle="--")
            story = _build_story_table(group)
            per_story_max.append(story[["story_idx", "z_bottom", "z_top", "drift_u1_max", "drift_u2_max"]])
            per_story_min.append(story[["story_idx", "z_bottom", "z_top", "drift_u1_min", "drift_u2_min"]])
            all_z.append(float(story["z_top"].max()))
        if per_story_max:
            mean_x = (
                pd.concat(per_story_max, ignore_index=True)
                .groupby("story_idx", as_index=False)[["z_bottom", "z_top", "drift_u1_max", "drift_u2_max"]]
                .mean()
                .sort_values("story_idx")
            )
            mean_y = (
                pd.concat(per_story_min, ignore_index=True)
                .groupby("story_idx", as_index=False)[["z_bottom", "z_top", "drift_u1_min", "drift_u2_min"]]
                .mean()
                .sort_values("story_idx")
            )
            coords_xm = {"x": [0.0], "y": [0.0]}
            for row in mean_x.itertuples(index=False):
                coords_xm["x"].extend([float(row.drift_u1_max), float(row.drift_u1_max)])
                coords_xm["y"].extend([float(row.z_bottom), float(row.z_top)])
            coords_xn = {"x": [0.0], "y": [0.0]}
            for row in mean_y.itertuples(index=False):
                coords_xn["x"].extend([float(row.drift_u1_min), float(row.drift_u1_min)])
                coords_xn["y"].extend([float(row.z_bottom), float(row.z_top)])
            ax_x.plot(coords_xm["x"], coords_xm["y"], color=color, linewidth=MEAN_WIDTH, label=f"{bundle['label']} max mean")
            ax_x.plot(coords_xn["x"], coords_xn["y"], color=color, linewidth=MEAN_WIDTH, linestyle="--", label=f"{bundle['label']} min mean")

            coords_ym = {"x": [0.0], "y": [0.0]}
            for row in mean_x.itertuples(index=False):
                coords_ym["x"].extend([float(row.drift_u2_max), float(row.drift_u2_max)])
                coords_ym["y"].extend([float(row.z_bottom), float(row.z_top)])
            coords_yn = {"x": [0.0], "y": [0.0]}
            for row in mean_y.itertuples(index=False):
                coords_yn["x"].extend([float(row.drift_u2_min), float(row.drift_u2_min)])
                coords_yn["y"].extend([float(row.z_bottom), float(row.z_top)])
            ax_y.plot(coords_ym["x"], coords_ym["y"], color=color, linewidth=MEAN_WIDTH, label=f"{bundle['label']} max mean")
            ax_y.plot(coords_yn["x"], coords_yn["y"], color=color, linewidth=MEAN_WIDTH, linestyle="--", label=f"{bundle['label']} min mean")

        all_dx.extend(df["drift_u1_max"].tolist())
        all_dx.extend(df["drift_u1_min"].tolist())
        all_dy.extend(df["drift_u2_max"].tolist())
        all_dy.extend(df["drift_u2_min"].tolist())

    ax_x.set_ylabel(f"Height ({length_unit})")
    ax_y.set_ylabel(f"Height ({length_unit})")
    _style_axis(ax_x, "Story Drift U1", "Story Drift Profile - X", show_titles)
    _style_axis(ax_y, "Story Drift U2", "Story Drift Profile - Y", show_titles)
    _set_limits_from_values(ax_x, all_dx, axis="x", symmetric=True)
    _set_limits_from_values(ax_y, all_dy, axis="x", symmetric=True)
    _set_limits_from_values(ax_x, all_z, axis="y", positive_y=True)
    _set_limits_from_values(ax_y, all_z, axis="y", positive_y=True)
    ax_x.legend(fontsize=8)
    ax_y.legend(fontsize=8)
    fig.tight_layout()
    return fig


def _fit_curve(x_values, y_values, degree: int, through_origin: bool = False):
    df = pd.DataFrame({"x": x_values, "y": y_values}).dropna()
    min_points = degree if through_origin else degree + 1
    if len(df.index) < min_points:
        return None
    if degree == 2 and through_origin:
        a_matrix = np.column_stack([df["x"] ** 2, df["x"]])
        coeffs_reduced, *_ = np.linalg.lstsq(a_matrix, df["y"], rcond=None)
        coeffs = np.array([coeffs_reduced[0], coeffs_reduced[1], 0.0], dtype=float)
    else:
        coeffs = np.polyfit(df["x"], df["y"], degree)
    poly = np.poly1d(coeffs)
    y_pred = poly(df["x"])
    ss_res = float(((df["y"] - y_pred) ** 2).sum())
    ss_tot = float(((df["y"] - df["y"].mean()) ** 2).sum())
    r2 = 1.0 if ss_tot == 0.0 else 1.0 - (ss_res / ss_tot)
    return coeffs, r2


def _format_equation(y_col: str, x_col: str, coeffs, through_origin: bool = False) -> str:
    if len(coeffs) == 2:
        slope, intercept = coeffs
        return f"{y_col} = {slope:.6g} * {x_col} + {intercept:.6g}"
    if len(coeffs) == 3:
        a2, a1, a0 = coeffs
        if through_origin and abs(a0) < 1e-12:
            return f"{y_col} = {a2:.6g} * {x_col}^2 + {a1:.6g} * {x_col}"
        return f"{y_col} = {a2:.6g} * {x_col}^2 + {a1:.6g} * {x_col} + {a0:.6g}"
    return f"{y_col} = poly({x_col})"


def _build_trend_xs(x_values, through_origin: bool):
    series = pd.Series(x_values).dropna()
    if series.empty:
        return series
    x_min = float(series.min())
    x_max = float(series.max())
    if through_origin:
        x_min = min(x_min, 0.0)
        x_max = max(x_max, 0.0)
    if abs(x_max - x_min) < 1e-12:
        return pd.Series([x_min, x_max])
    return pd.Series(np.linspace(x_min, x_max, 200))


def _build_scatter_df(bundle):
    df_nodes = bundle["node_disp"]
    df_summary = bundle["run_summary"]
    if df_nodes.empty or df_summary.empty:
        return pd.DataFrame()
    disp = (
        df_nodes.groupby("run_id", as_index=False)
        .agg(
            disp_x_max=("u1_max", "max"),
            disp_x_min=("u1_min", "min"),
            disp_y_max=("u2_max", "max"),
            disp_y_min=("u2_min", "min"),
        )
    )
    return disp.merge(df_summary, on="run_id", how="inner")


def _build_abs_envelope(points_df: pd.DataFrame) -> pd.DataFrame:
    clean = points_df[["disp_abs", "shear_abs"]].dropna().copy()
    if clean.empty:
        return clean
    clean = clean.sort_values("disp_abs")
    grouped = clean.groupby("disp_abs", as_index=False)["shear_abs"].max().sort_values("disp_abs")
    grouped["shear_env"] = grouped["shear_abs"].cummax()
    return grouped


def _plot_scatter_abs_direction(
    bundles,
    length_unit: str,
    force_unit: str,
    show_titles: bool,
    show_trend_lines: bool,
    quadratic_trend: bool,
    quadratic_through_origin: bool,
    direction: str,
):
    fig, ax = plt.subplots(figsize=(8, 6))
    all_x = []
    all_y = []
    legend_handles = []
    fit_rows = []
    x_max_col = f"disp_{direction.lower()}_max"
    x_min_col = f"disp_{direction.lower()}_min"
    y_max_col = f"max_v{direction.lower()}_base"
    y_min_col = f"min_v{direction.lower()}_base"

    for bundle in bundles:
        df = _build_scatter_df(bundle)
        if df.empty:
            continue
        color = DB_COLORS.get(bundle["label"], None)
        points = pd.DataFrame(
            {
                "disp_abs": pd.concat([df[x_max_col].abs(), df[x_min_col].abs()], ignore_index=True),
                "shear_abs": pd.concat([df[y_max_col].abs(), df[y_min_col].abs()], ignore_index=True),
            }
        ).dropna()
        if points.empty:
            continue
        ax.scatter(points["disp_abs"], points["shear_abs"], color=color, marker="o", s=26, alpha=0.25)
        env = _build_abs_envelope(points)
        if not env.empty:
            ax.plot(env["disp_abs"], env["shear_env"], color=color, linewidth=MEAN_WIDTH)
        if quadratic_trend and quadratic_through_origin:
            fit = _fit_curve(points["disp_abs"], points["shear_abs"], 2, through_origin=True)
            if fit is not None:
                coeffs, r2 = fit
                xs = _build_trend_xs(points["disp_abs"], through_origin=True)
                poly = np.poly1d(coeffs)
                ys = poly(xs)
                if show_trend_lines:
                    ax.plot(xs, ys, color=color, linewidth=2.0, linestyle="--")
                fit_rows.append(
                    {
                        "db_label": bundle["label"],
                        "direction": direction,
                        "envelope": "abs",
                        "trend_degree": 2,
                        "through_origin": True,
                        "coeff_2": coeffs[0],
                        "coeff_1": coeffs[1],
                        "intercept": coeffs[2],
                        "r2": r2,
                        "equation": _format_equation("shear_abs", "disp_abs", coeffs, through_origin=True),
                    }
                )
        legend_handles.append(
            Line2D(
                [0],
                [0],
                color=color,
                linestyle="-",
                linewidth=2.5,
                marker="o",
                markersize=6,
                markerfacecolor=color,
                markeredgecolor=color,
                alpha=1.0,
                label=f"{bundle['label']} envelope",
            )
        )
        all_x.extend(points["disp_abs"].tolist())
        all_y.extend(points["shear_abs"].tolist())

    _style_axis(
        ax,
        f"|Maximum Roof Displacement {direction}| ({length_unit})",
        f"|Base Shear {direction}| vs |Maximum Roof Displacement {direction}|",
        show_titles,
    )
    ax.set_ylabel(f"|Base Shear {direction}| ({force_unit})")
    _set_limits_from_values(ax, all_x, axis="x", positive_y=True)
    _set_limits_from_values(ax, all_y, axis="y", positive_y=True)
    ax.legend(handles=legend_handles, fontsize=8, ncol=1)
    fig.tight_layout()
    return fig, pd.DataFrame(fit_rows)


def _plot_scatter_direction(
    bundles,
    length_unit: str,
    force_unit: str,
    show_titles: bool,
    show_trend_lines: bool,
    quadratic_trend: bool,
    quadratic_through_origin: bool,
    direction: str,
):
    fig, ax = plt.subplots(figsize=(8, 6))
    all_x = []
    all_y = []
    fit_rows = []
    legend_handles = []
    trend_degree = 2 if quadratic_trend else 1
    specs = [
        (direction, "max", f"disp_{direction.lower()}_max", f"max_v{direction.lower()}_base"),
        (direction, "min", f"disp_{direction.lower()}_min", f"min_v{direction.lower()}_base"),
    ]

    for bundle in bundles:
        df = _build_scatter_df(bundle)
        if df.empty:
            continue
        color = DB_COLORS.get(bundle["label"], None)
        for direction_name, envelope, x_col, y_col in specs:
            marker = MARKERS[(direction_name, envelope)]
            linestyle = LINESTYLES[(direction_name, envelope)]
            label = f"{bundle['label']} {direction_name} {envelope}"
            ax.scatter(df[x_col], df[y_col], color=color, marker=marker, s=30, alpha=0.3)
            legend_handles.append(
                Line2D(
                    [0],
                    [0],
                    color=color,
                    linestyle=linestyle,
                    linewidth=2.0,
                    marker=marker,
                    markersize=6,
                    markerfacecolor=color,
                    markeredgecolor=color,
                    alpha=1.0,
                    label=label,
                )
            )
            fit = _fit_curve(df[x_col], df[y_col], trend_degree, through_origin=(quadratic_trend and quadratic_through_origin))
            if fit is not None:
                coeffs, r2 = fit
                xs = _build_trend_xs(df[x_col], through_origin=(quadratic_trend and quadratic_through_origin))
                poly = np.poly1d(coeffs)
                ys = poly(xs)
                if show_trend_lines:
                    ax.plot(xs, ys, color=color, linewidth=2.5, linestyle=linestyle)
                fit_rows.append(
                    {
                        "db_label": bundle["label"],
                        "direction": direction_name,
                        "envelope": envelope,
                        "trend_degree": trend_degree,
                        "through_origin": bool(quadratic_trend and quadratic_through_origin),
                        "coeff_2": coeffs[0] if len(coeffs) == 3 else np.nan,
                        "coeff_1": coeffs[-2],
                        "intercept": coeffs[-1],
                        "r2": r2,
                        "equation": _format_equation(y_col, x_col, coeffs, through_origin=(quadratic_trend and quadratic_through_origin)),
                    }
                )
            all_x.extend(df[x_col].tolist())
            all_y.extend(df[y_col].tolist())

    _style_axis(
        ax,
        f"Maximum Roof Displacement {direction} ({length_unit})",
        f"Base Shear {direction} vs Maximum Roof Displacement {direction}",
        show_titles,
    )
    ax.set_ylabel(f"Base Shear {direction} ({force_unit})")
    _set_limits_from_values(ax, all_x, axis="x", symmetric=True)
    _set_limits_from_values(ax, all_y, axis="y", symmetric=True)
    ax.legend(handles=legend_handles, fontsize=8, ncol=2)
    fig.tight_layout()
    return fig, pd.DataFrame(fit_rows)


def _plot_scatter(bundles, length_unit: str, force_unit: str, show_titles: bool, show_trend_lines: bool, quadratic_trend: bool, quadratic_through_origin: bool):
    fig, ax = plt.subplots(figsize=(8, 6))
    all_x = []
    all_y = []
    fit_rows = []
    legend_handles = []
    trend_degree = 2 if quadratic_trend else 1

    for bundle in bundles:
        df = _build_scatter_df(bundle)
        if df.empty:
            continue
        color = DB_COLORS.get(bundle["label"], None)
        specs = [
            ("X", "max", "disp_x_max", "max_vx_base"),
            ("X", "min", "disp_x_min", "min_vx_base"),
            ("Y", "max", "disp_y_max", "max_vy_base"),
            ("Y", "min", "disp_y_min", "min_vy_base"),
        ]
        for direction, envelope, x_col, y_col in specs:
            marker = MARKERS[(direction, envelope)]
            linestyle = LINESTYLES[(direction, envelope)]
            label = f"{bundle['label']} {direction} {envelope}"
            ax.scatter(df[x_col], df[y_col], color=color, marker=marker, s=30, alpha=0.3)
            legend_handles.append(
                Line2D(
                    [0],
                    [0],
                    color=color,
                    linestyle=linestyle,
                    linewidth=2.0,
                    marker=marker,
                    markersize=6,
                    markerfacecolor=color,
                    markeredgecolor=color,
                    alpha=1.0,
                    label=label,
                )
            )
            fit = _fit_curve(df[x_col], df[y_col], trend_degree, through_origin=(quadratic_trend and quadratic_through_origin))
            if fit is not None:
                coeffs, r2 = fit
                xs = _build_trend_xs(df[x_col], through_origin=(quadratic_trend and quadratic_through_origin))
                poly = np.poly1d(coeffs)
                ys = poly(xs)
                if show_trend_lines:
                    ax.plot(xs, ys, color=color, linewidth=2.5, linestyle=linestyle)
                fit_rows.append({
                    "db_label": bundle["label"],
                    "direction": direction,
                    "envelope": envelope,
                    "trend_degree": trend_degree,
                    "through_origin": bool(quadratic_trend and quadratic_through_origin),
                    "coeff_2": coeffs[0] if len(coeffs) == 3 else np.nan,
                    "coeff_1": coeffs[-2],
                    "intercept": coeffs[-1],
                    "r2": r2,
                    "equation": _format_equation(y_col, x_col, coeffs, through_origin=(quadratic_trend and quadratic_through_origin)),
                })
            all_x.extend(df[x_col].tolist())
            all_y.extend(df[y_col].tolist())

    _style_axis(ax, f"Maximum Displacement ({length_unit})", "Base Shear vs Maximum Displacement", show_titles)
    ax.set_ylabel(f"Base Shear ({force_unit})")
    _set_limits_from_values(ax, all_x, axis="x", symmetric=True)
    _set_limits_from_values(ax, all_y, axis="y", symmetric=True)
    ax.legend(handles=legend_handles, fontsize=8, ncol=2)
    fig.tight_layout()
    return fig, pd.DataFrame(fit_rows)


def _export_figure(fig, export_dir: Path, base_name: str):
    export_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(export_dir / f"{base_name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(export_dir / f"{base_name}.pdf", bbox_inches="tight")


def main():
    args = _parse_args()
    results_dirs = [Path(p).resolve() for p in (args.results_dirs or DEFAULT_RESULTS_DIRS)]
    labels = args.labels or DEFAULT_LABELS[: len(results_dirs)]
    if len(labels) != len(results_dirs):
        raise ValueError("--label must be provided the same number of times as --results-dir")

    bundles = [_load_db_bundle(rd, label) for rd, label in zip(results_dirs, labels)]
    settings_path = _guess_settings_path(args.settings_path, results_dirs)
    length_unit, force_unit = _resolve_units(settings_path)
    export_dir = Path(args.export_dir).resolve() if args.export_dir else results_dirs[0] / "figures_multi"

    fig_disp = _plot_displacement(bundles, length_unit, not args.hide_titles)
    fig_drift = _plot_drift(bundles, length_unit, not args.hide_titles)
    fig_scatter, fit_df = _plot_scatter(
        bundles,
        length_unit,
        force_unit,
        not args.hide_titles,
        not args.hide_trend_lines,
        args.quadratic_trend,
        args.quadratic_through_origin,
    )
    fig_scatter_x, fit_df_x = _plot_scatter_direction(
        bundles,
        length_unit,
        force_unit,
        not args.hide_titles,
        not args.hide_trend_lines,
        args.quadratic_trend,
        args.quadratic_through_origin,
        "X",
    )
    fig_scatter_y, fit_df_y = _plot_scatter_direction(
        bundles,
        length_unit,
        force_unit,
        not args.hide_titles,
        not args.hide_trend_lines,
        args.quadratic_trend,
        args.quadratic_through_origin,
        "Y",
    )
    fig_scatter_abs_x, fit_df_abs_x = _plot_scatter_abs_direction(
        bundles,
        length_unit,
        force_unit,
        not args.hide_titles,
        not args.hide_trend_lines,
        args.quadratic_trend,
        args.quadratic_through_origin,
        "X",
    )
    fig_scatter_abs_y, fit_df_abs_y = _plot_scatter_abs_direction(
        bundles,
        length_unit,
        force_unit,
        not args.hide_titles,
        not args.hide_trend_lines,
        args.quadratic_trend,
        args.quadratic_through_origin,
        "Y",
    )

    _export_figure(fig_disp, export_dir, "multi_displacement_profiles")
    _export_figure(fig_drift, export_dir, "multi_drift_profiles")
    _export_figure(fig_scatter, export_dir, "multi_base_shear_vs_displacement")
    _export_figure(fig_scatter_x, export_dir, "multi_base_shear_vs_displacement_x")
    _export_figure(fig_scatter_y, export_dir, "multi_base_shear_vs_displacement_y")
    _export_figure(fig_scatter_abs_x, export_dir, "multi_base_shear_vs_displacement_abs_x")
    _export_figure(fig_scatter_abs_y, export_dir, "multi_base_shear_vs_displacement_abs_y")
    if not fit_df.empty:
        fit_df.to_csv(export_dir / "multi_linear_fit_summary.csv", index=False)
        print(f"Exported: {export_dir / 'multi_linear_fit_summary.csv'}")
    fit_df_dir = pd.concat([fit_df_x, fit_df_y], ignore_index=True)
    if not fit_df_dir.empty:
        fit_df_dir.to_csv(export_dir / "multi_linear_fit_summary_by_direction.csv", index=False)
        print(f"Exported: {export_dir / 'multi_linear_fit_summary_by_direction.csv'}")
    fit_df_abs = pd.concat([fit_df_abs_x, fit_df_abs_y], ignore_index=True)
    if not fit_df_abs.empty:
        fit_df_abs.to_csv(export_dir / "multi_abs_quadratic_fit_summary_by_direction.csv", index=False)
        print(f"Exported: {export_dir / 'multi_abs_quadratic_fit_summary_by_direction.csv'}")

    plt.show()


if __name__ == "__main__":
    main()
