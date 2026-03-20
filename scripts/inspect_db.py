from pathlib import Path
import sys
import argparse
import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs.nodes_config import load_nodes_config
from solvers.sap2000.units import infer_force_unit_label, infer_length_unit_label

RUN_COLOR = "0.70"
MEAN_COLOR = "0.15"
RUN_WIDTH = 0.8
MEAN_WIDTH = 2.0
SCATTER_X_COLOR = "#4C78A8"
SCATTER_Y_COLOR = "#F51818"


def _parse_args():
    parser = argparse.ArgumentParser(description="Inspect ETABSlab SQLite results")
    parser.add_argument("--db", dest="db_path", default=None, help="Path to edp.sqlite")
    parser.add_argument(
        "--results-dir",
        dest="results_dir",
        default=None,
        help="Results folder containing edp.sqlite",
    )
    parser.add_argument("--run-id", dest="run_id", type=int, default=None, help="Specific run ID")
    parser.add_argument(
        "--export-dir",
        dest="export_dir",
        default=None,
        help="Directory to export figures as PNG and PDF",
    )
    parser.add_argument(
        "--settings",
        dest="settings_path",
        default=None,
        help="Path to settings.yaml used to infer output units",
    )
    parser.add_argument(
        "--hide-titles",
        dest="hide_titles",
        action="store_true",
        help="Hide plot titles",
    )
    parser.add_argument(
        "--xlim",
        dest="xlim",
        nargs=2,
        type=float,
        default=None,
        metavar=("XMIN", "XMAX"),
        help="Override X-axis limits for all plots",
    )
    parser.add_argument(
        "--ylim",
        dest="ylim",
        nargs=2,
        type=float,
        default=None,
        metavar=("YMIN", "YMAX"),
        help="Override Y-axis limits for all plots",
    )
    parser.add_argument("--disp-xlim", dest="disp_xlim", nargs=2, type=float, default=None, metavar=("XMIN", "XMAX"))
    parser.add_argument("--disp-ylim", dest="disp_ylim", nargs=2, type=float, default=None, metavar=("YMIN", "YMAX"))
    parser.add_argument("--drift-xlim", dest="drift_xlim", nargs=2, type=float, default=None, metavar=("XMIN", "XMAX"))
    parser.add_argument("--drift-ylim", dest="drift_ylim", nargs=2, type=float, default=None, metavar=("YMIN", "YMAX"))
    parser.add_argument("--scatter-xlim", dest="scatter_xlim", nargs=2, type=float, default=None, metavar=("XMIN", "XMAX"))
    parser.add_argument("--scatter-ylim", dest="scatter_ylim", nargs=2, type=float, default=None, metavar=("YMIN", "YMAX"))
    return parser.parse_args()


def _get_db_path(db_path: str | None = None, results_dir: str | None = None):
    if db_path:
        return Path(db_path).resolve()
    if results_dir:
        return Path(results_dir).resolve() / "edp.sqlite"
    return Path("results").resolve() / "edp.sqlite"


def _guess_settings_path(args) -> Path | None:
    if args.settings_path:
        path = Path(args.settings_path).resolve()
        return path if path.exists() else None

    candidates = []
    if args.results_dir:
        results_dir = Path(args.results_dir).resolve()
        candidates.extend(
            [
                results_dir.parent / "settings.yaml",
                results_dir.parent / "config" / "settings.yaml",
            ]
        )
    candidates.append((ROOT / "config" / "settings.yaml").resolve())

    for path in candidates:
        if path.exists():
            return path.resolve()
    return None


def _resolve_unit_labels(args):
    settings_path = _guess_settings_path(args)
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

    length_unit = infer_length_unit_label(output_units) or "cm"
    force_unit = infer_force_unit_label(output_units) or "force units"
    return length_unit, force_unit


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


def _style_axis(ax, xlabel: str, title: str, show_titles: bool):
    ax.set_xlabel(xlabel)
    if show_titles:
        ax.set_title(title)
    ax.grid(True, linestyle="--", alpha=0.35, linewidth=0.6)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=5))


def _apply_manual_limits(ax, xlim=None, ylim=None):
    if xlim is not None:
        ax.set_xlim(float(xlim[0]), float(xlim[1]))
    if ylim is not None:
        ax.set_ylim(float(ylim[0]), float(ylim[1]))


def _set_y_limits(ax, values):
    if values is None:
        return
    series = pd.Series(list(values)).dropna()
    if series.empty:
        return
    ymax = float(series.max())
    if ymax <= 0.0:
        ymax = 1.0
    ax.set_ylim(0.0, ymax)


def _set_signed_limits(ax, values, axis="x"):
    if values is None:
        return
    series = pd.Series(list(values)).dropna()
    if series.empty:
        return
    vmin = float(series.min())
    vmax = float(series.max())
    if vmin == vmax:
        if vmax == 0.0:
            vmin, vmax = -1.0, 1.0
        else:
            pad = 0.05 * abs(vmax)
            vmin -= pad
            vmax += pad
    else:
        pad = 0.05 * max(abs(vmin), abs(vmax), 1.0)
        vmin -= pad
        vmax += pad
    if axis == "x":
        ax.set_xlim(vmin, vmax)
    else:
        ax.set_ylim(vmin, vmax)


def _set_symmetric_limits(ax, values, axis="x"):
    if values is None:
        return
    series = pd.Series(list(values)).dropna()
    if series.empty:
        return
    limit = float(series.abs().max())
    if limit <= 0.0:
        limit = 1.0
    pad = 0.05 * limit
    lower = -(limit + pad)
    upper = limit + pad
    if axis == "x":
        ax.set_xlim(lower, upper)
    else:
        ax.set_ylim(lower, upper)


def _plot_node_disp(df_nodes, length_unit: str, plot_opts: dict):
    if df_nodes.empty:
        print("No hay node_disp para graficar.")
        return

    df_nodes = df_nodes.sort_values(["run_id", "z"]).copy()
    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(10, 5), sharey=True)
    ax_x, ax_y = axes

    for _, group in df_nodes.groupby("run_id"):
        ax_x.plot(
            group["u1_max"],
            group["z"],
            color=RUN_COLOR,
            linewidth=RUN_WIDTH,
        )
        ax_x.plot(
            group["u1_min"],
            group["z"],
            color=RUN_COLOR,
            linewidth=RUN_WIDTH,
            linestyle="--",
        )
        ax_y.plot(
            group["u2_max"],
            group["z"],
            color=RUN_COLOR,
            linewidth=RUN_WIDTH,
        )
        ax_y.plot(
            group["u2_min"],
            group["z"],
            color=RUN_COLOR,
            linewidth=RUN_WIDTH,
            linestyle="--",
        )

    mean_nodes = (
        df_nodes.groupby("z", as_index=False)[["u1_max", "u1_min", "u2_max", "u2_min"]]
        .mean()
        .sort_values("z")
    )
    ax_x.plot(
        mean_nodes["u1_max"],
        mean_nodes["z"],
        color=MEAN_COLOR,
        linewidth=MEAN_WIDTH,
        label="Max mean",
    )
    ax_x.plot(
        mean_nodes["u1_min"],
        mean_nodes["z"],
        color=MEAN_COLOR,
        linewidth=MEAN_WIDTH,
        linestyle="--",
        label="Min mean",
    )
    ax_y.plot(
        mean_nodes["u2_max"],
        mean_nodes["z"],
        color=MEAN_COLOR,
        linewidth=MEAN_WIDTH,
        label="Max mean",
    )
    ax_y.plot(
        mean_nodes["u2_min"],
        mean_nodes["z"],
        color=MEAN_COLOR,
        linewidth=MEAN_WIDTH,
        linestyle="--",
        label="Min mean",
    )

    ax_x.set_ylabel(f"Height ({length_unit})")
    _style_axis(
        ax_x,
        f"U1 Displacement ({length_unit})",
        "Displacement Profile - X",
        show_titles=plot_opts["show_titles"],
    )
    _style_axis(
        ax_y,
        f"U2 Displacement ({length_unit})",
        "Displacement Profile - Y",
        show_titles=plot_opts["show_titles"],
    )
    ax_x.legend()
    ax_y.legend()
    _set_signed_limits(
        ax_x,
        pd.concat([df_nodes["u1_max"], df_nodes["u1_min"]], ignore_index=True),
    )
    _set_signed_limits(
        ax_y,
        pd.concat([df_nodes["u2_max"], df_nodes["u2_min"]], ignore_index=True),
    )
    _set_y_limits(ax_x, df_nodes["z"])
    _set_y_limits(ax_y, df_nodes["z"])
    _apply_manual_limits(ax_x, xlim=plot_opts["xlim"], ylim=plot_opts["ylim"])
    _apply_manual_limits(ax_y, xlim=plot_opts["xlim"], ylim=plot_opts["ylim"])
    fig.tight_layout()
    return fig


def _build_step_profile(group: pd.DataFrame, value_col: str):
    ordered = group.reset_index(drop=True).copy()
    cumulative_height = 0.0
    x = [0.0]
    y = [0.0]
    story_rows = []

    for story_idx, row in ordered.iterrows():
        bottom = cumulative_height
        top = cumulative_height + float(row["dz"])
        value = float(row[value_col])
        x.extend([value, value])
        y.extend([bottom, top])
        story_rows.append(
            {
                "story_idx": story_idx,
                "z_bottom": bottom,
                "z_top": top,
                value_col: value,
            }
        )
        cumulative_height = top

    return x, y, pd.DataFrame(story_rows)


def _plot_step_profiles(
    ax,
    df_drifts,
    value_col_max: str,
    value_col_min: str,
    xlabel: str,
    title: str,
    show_titles: bool,
):
    story_profiles_max = []
    story_profiles_min = []

    for _, group in df_drifts.groupby("run_id"):
        x_max, y_max, story_df_max = _build_step_profile(group, value_col_max)
        x_min, y_min, story_df_min = _build_step_profile(group, value_col_min)
        story_profiles_max.append(story_df_max)
        story_profiles_min.append(story_df_min)
        ax.plot(x_max, y_max, color=RUN_COLOR, linewidth=RUN_WIDTH)
        ax.plot(x_min, y_min, color=RUN_COLOR, linewidth=RUN_WIDTH, linestyle="--")

    if story_profiles_max:
        mean_df_max = pd.concat(story_profiles_max, ignore_index=True)
        mean_df_max = (
            mean_df_max.groupby(["story_idx", "z_bottom", "z_top"], as_index=False)[value_col_max]
            .mean()
            .sort_values("story_idx")
        )
        x_mean_max = [0.0]
        y_mean_max = [0.0]
        for row in mean_df_max.itertuples(index=False):
            x_mean_max.extend(
                [float(getattr(row, value_col_max)), float(getattr(row, value_col_max))]
            )
            y_mean_max.extend([float(row.z_bottom), float(row.z_top)])
        ax.plot(
            x_mean_max,
            y_mean_max,
            color=MEAN_COLOR,
            linewidth=MEAN_WIDTH,
            label="Max mean",
        )

    if story_profiles_min:
        mean_df_min = pd.concat(story_profiles_min, ignore_index=True)
        mean_df_min = (
            mean_df_min.groupby(["story_idx", "z_bottom", "z_top"], as_index=False)[value_col_min]
            .mean()
            .sort_values("story_idx")
        )
        x_mean_min = [0.0]
        y_mean_min = [0.0]
        for row in mean_df_min.itertuples(index=False):
            x_mean_min.extend(
                [float(getattr(row, value_col_min)), float(getattr(row, value_col_min))]
            )
            y_mean_min.extend([float(row.z_bottom), float(row.z_top)])
        ax.plot(
            x_mean_min,
            y_mean_min,
            color=MEAN_COLOR,
            linewidth=MEAN_WIDTH,
            linestyle="--",
            label="Min mean",
        )

    _style_axis(ax, xlabel, title, show_titles=show_titles)
    ax.legend()


def _plot_drifts(df_drifts, length_unit: str, plot_opts: dict):
    if df_drifts.empty:
        print("No hay drifts para graficar.")
        return

    df_drifts = df_drifts.sort_values(["run_id"]).copy()
    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(10, 5), sharey=True)
    ax_x, ax_y = axes

    _plot_step_profiles(
        ax_x,
        df_drifts,
        "drift_u1_max",
        "drift_u1_min",
        "Story Drift U1",
        "Story Drift Profile - X",
        show_titles=plot_opts["show_titles"],
    )
    _plot_step_profiles(
        ax_y,
        df_drifts,
        "drift_u2_max",
        "drift_u2_min",
        "Story Drift U2",
        "Story Drift Profile - Y",
        show_titles=plot_opts["show_titles"],
    )

    ax_x.set_ylabel(f"Height ({length_unit})")
    _set_symmetric_limits(
        ax_x,
        pd.concat([df_drifts["drift_u1_max"], df_drifts["drift_u1_min"]], ignore_index=True),
    )
    _set_symmetric_limits(
        ax_y,
        pd.concat([df_drifts["drift_u2_max"], df_drifts["drift_u2_min"]], ignore_index=True),
    )
    drift_heights = (
        df_drifts.groupby("run_id")["dz"]
        .sum()
        .astype(float)
    )
    _set_y_limits(ax_x, drift_heights)
    _set_y_limits(ax_y, drift_heights)
    _apply_manual_limits(ax_x, xlim=plot_opts["xlim"], ylim=plot_opts["ylim"])
    _apply_manual_limits(ax_y, xlim=plot_opts["xlim"], ylim=plot_opts["ylim"])
    fig.tight_layout()
    return fig


def _export_figure(fig, export_dir: Path, base_name: str):
    export_dir.mkdir(parents=True, exist_ok=True)
    png_path = export_dir / f"{base_name}.png"
    pdf_path = export_dir / f"{base_name}.pdf"
    fig.savefig(png_path, dpi=200, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    print(f"Exported: {png_path}")
    print(f"Exported: {pdf_path}")


def _export_table(df: pd.DataFrame, export_dir: Path, base_name: str):
    if df is None or df.empty:
        return
    export_dir.mkdir(parents=True, exist_ok=True)
    csv_path = export_dir / f"{base_name}.csv"
    df.to_csv(csv_path, index=False)
    print(f"Exported: {csv_path}")


def _build_node_disp_summary(df_nodes):
    if df_nodes.empty:
        return pd.DataFrame()
    summary = (
        df_nodes.groupby("z", as_index=False)
        .agg(
            u1_max_min=("u1_max", "min"),
            u1_max_mean=("u1_max", "mean"),
            u1_max_max=("u1_max", "max"),
            u1_min_min=("u1_min", "min"),
            u1_min_mean=("u1_min", "mean"),
            u1_min_max=("u1_min", "max"),
            u2_max_min=("u2_max", "min"),
            u2_max_mean=("u2_max", "mean"),
            u2_max_max=("u2_max", "max"),
            u2_min_min=("u2_min", "min"),
            u2_min_mean=("u2_min", "mean"),
            u2_min_max=("u2_min", "max"),
        )
        .sort_values("z")
    )
    return summary


def _build_drift_story_table(df_drifts):
    rows = []
    for run_id, group in df_drifts.groupby("run_id"):
        ordered = group.reset_index(drop=True).copy()
        cumulative_height = 0.0
        for story_idx, row in ordered.iterrows():
            bottom = cumulative_height
            top = cumulative_height + float(row["dz"])
            rows.append(
                {
                    "run_id": run_id,
                    "story_idx": story_idx,
                    "z_bottom": bottom,
                    "z_top": top,
                    "drift_u1_max": float(row["drift_u1_max"]),
                    "drift_u1_min": float(row["drift_u1_min"]),
                    "drift_u2_max": float(row["drift_u2_max"]),
                    "drift_u2_min": float(row["drift_u2_min"]),
                }
            )
            cumulative_height = top
    return pd.DataFrame(rows)


def _build_drift_summary(df_drifts):
    if df_drifts.empty:
        return pd.DataFrame()
    story_df = _build_drift_story_table(df_drifts)
    summary = (
        story_df.groupby(["story_idx", "z_bottom", "z_top"], as_index=False)
        .agg(
            drift_u1_max_min=("drift_u1_max", "min"),
            drift_u1_max_mean=("drift_u1_max", "mean"),
            drift_u1_max_max=("drift_u1_max", "max"),
            drift_u1_min_min=("drift_u1_min", "min"),
            drift_u1_min_mean=("drift_u1_min", "mean"),
            drift_u1_min_max=("drift_u1_min", "max"),
            drift_u2_max_min=("drift_u2_max", "min"),
            drift_u2_max_mean=("drift_u2_max", "mean"),
            drift_u2_max_max=("drift_u2_max", "max"),
            drift_u2_min_min=("drift_u2_min", "min"),
            drift_u2_min_mean=("drift_u2_min", "mean"),
            drift_u2_min_max=("drift_u2_min", "max"),
        )
        .sort_values("story_idx")
    )
    return summary


def _fit_linear(x_values, y_values):
    df = pd.DataFrame({"x": x_values, "y": y_values}).dropna()
    if len(df.index) < 2:
        return None
    slope, intercept = np.polyfit(df["x"], df["y"], 1)
    y_pred = slope * df["x"] + intercept
    ss_res = float(((df["y"] - y_pred) ** 2).sum())
    ss_tot = float(((df["y"] - df["y"].mean()) ** 2).sum())
    r2 = 1.0 if ss_tot == 0.0 else 1.0 - (ss_res / ss_tot)
    return {
        "x": df["x"],
        "y": df["y"],
        "slope": float(slope),
        "intercept": float(intercept),
        "r2": float(r2),
        "n_points": int(len(df.index)),
    }


def _build_base_shear_scatter_data(df_nodes, df_summary):
    if df_nodes.empty or df_summary.empty:
        return pd.DataFrame()
    disp_by_run = (
        df_nodes.groupby("run_id", as_index=False)
        .agg(
            disp_x_max=("u1_max", "max"),
            disp_x_min=("u1_min", "min"),
            disp_y_max=("u2_max", "max"),
            disp_y_min=("u2_min", "min"),
        )
    )
    return disp_by_run.merge(df_summary, on="run_id", how="inner")


def _build_fit_summary(scatter_df):
    if scatter_df.empty:
        return pd.DataFrame()
    fit_specs = [
        ("X", "max", "disp_x_max", "max_vx_base", "Vx", "Ux"),
        ("X", "min", "disp_x_min", "min_vx_base", "Vx_min", "Ux_min"),
        ("Y", "max", "disp_y_max", "max_vy_base", "Vy", "Uy"),
        ("Y", "min", "disp_y_min", "min_vy_base", "Vy_min", "Uy_min"),
    ]
    rows = []
    for direction, envelope, x_col, y_col, y_name, x_name in fit_specs:
        fit = _fit_linear(scatter_df[x_col], scatter_df[y_col])
        if fit is None:
            rows.append(
                {
                    "direction": direction,
                    "envelope": envelope,
                    "x_col": x_col,
                    "y_col": y_col,
                    "n_points": 0,
                    "slope": None,
                    "intercept": None,
                    "r2": None,
                    "equation": "not enough points",
                }
            )
            continue
        rows.append(
            {
                "direction": direction,
                "envelope": envelope,
                "x_col": x_col,
                "y_col": y_col,
                "n_points": fit["n_points"],
                "slope": fit["slope"],
                "intercept": fit["intercept"],
                "r2": fit["r2"],
                "equation": f"{y_name} = {fit['slope']:.6g} * {x_name} + {fit['intercept']:.6g}",
            }
        )
    return pd.DataFrame(rows)


def _plot_base_shear_vs_disp(df_nodes, df_summary, length_unit: str, force_unit: str, plot_opts: dict):
    if df_nodes.empty or df_summary.empty:
        print("No hay datos suficientes para graficar base shear vs displacement.")
        return None, pd.DataFrame(), pd.DataFrame()

    scatter_df = _build_base_shear_scatter_data(df_nodes, df_summary)
    if scatter_df.empty:
        print("No hay interseccion entre node_disp y run_summary para la grafica scatter.")
        return None, pd.DataFrame(), pd.DataFrame()

    fit_summary = _build_fit_summary(scatter_df)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(
        scatter_df["disp_x_max"],
        scatter_df["max_vx_base"],
        color=SCATTER_X_COLOR,
        s=24,
        alpha=0.9,
        label="X max",
    )
    ax.scatter(
        scatter_df["disp_y_max"],
        scatter_df["max_vy_base"],
        color=SCATTER_Y_COLOR,
        s=24,
        alpha=0.9,
        label="Y max",
    )
    ax.scatter(
        scatter_df["disp_x_min"],
        scatter_df["min_vx_base"],
        color=SCATTER_X_COLOR,
        marker="x",
        s=28,
        alpha=0.9,
        label="X min",
    )
    ax.scatter(
        scatter_df["disp_y_min"],
        scatter_df["min_vy_base"],
        color=SCATTER_Y_COLOR,
        marker="x",
        s=28,
        alpha=0.9,
        label="Y min",
    )

    fit_x = _fit_linear(scatter_df["disp_x_max"], scatter_df["max_vx_base"])
    fit_y = _fit_linear(scatter_df["disp_y_max"], scatter_df["max_vy_base"])
    fit_x_min = _fit_linear(scatter_df["disp_x_min"], scatter_df["min_vx_base"])
    fit_y_min = _fit_linear(scatter_df["disp_y_min"], scatter_df["min_vy_base"])

    if fit_x is not None:
        x_line = pd.Series(fit_x["x"]).sort_values()
        y_line = fit_x["slope"] * x_line + fit_x["intercept"]
        ax.plot(x_line, y_line, color=SCATTER_X_COLOR, linewidth=1.8)
        print(
            "Linear fit X: "
            f"Vx = {fit_x['slope']:.6g} * Ux + {fit_x['intercept']:.6g} | "
            f"R2 = {fit_x['r2']:.6f}"
        )
    else:
        print("Linear fit X: not enough points.")

    if fit_y is not None:
        x_line = pd.Series(fit_y["x"]).sort_values()
        y_line = fit_y["slope"] * x_line + fit_y["intercept"]
        ax.plot(x_line, y_line, color=SCATTER_Y_COLOR, linewidth=1.8)
        print(
            "Linear fit Y: "
            f"Vy = {fit_y['slope']:.6g} * Uy + {fit_y['intercept']:.6g} | "
            f"R2 = {fit_y['r2']:.6f}"
        )
    else:
        print("Linear fit Y: not enough points.")

    if fit_x_min is not None:
        x_line = pd.Series(fit_x_min["x"]).sort_values()
        y_line = fit_x_min["slope"] * x_line + fit_x_min["intercept"]
        ax.plot(x_line, y_line, color=SCATTER_X_COLOR, linewidth=1.8, linestyle="--")
        print(
            "Linear fit X min: "
            f"Vx_min = {fit_x_min['slope']:.6g} * Ux_min + {fit_x_min['intercept']:.6g} | "
            f"R2 = {fit_x_min['r2']:.6f}"
        )
    else:
        print("Linear fit X min: not enough points.")

    if fit_y_min is not None:
        x_line = pd.Series(fit_y_min["x"]).sort_values()
        y_line = fit_y_min["slope"] * x_line + fit_y_min["intercept"]
        ax.plot(x_line, y_line, color=SCATTER_Y_COLOR, linewidth=1.8, linestyle="--")
        print(
            "Linear fit Y min: "
            f"Vy_min = {fit_y_min['slope']:.6g} * Uy_min + {fit_y_min['intercept']:.6g} | "
            f"R2 = {fit_y_min['r2']:.6f}"
        )
    else:
        print("Linear fit Y min: not enough points.")

    _style_axis(
        ax,
        f"Maximum Displacement ({length_unit})",
        "Base Shear vs Maximum Displacement",
        show_titles=plot_opts["show_titles"],
    )
    ax.set_ylabel(f"Maximum Base Shear ({force_unit})")
    ax.legend()
    _set_signed_limits(
        ax,
        pd.concat(
            [
                scatter_df["disp_x_max"],
                scatter_df["disp_x_min"],
                scatter_df["disp_y_max"],
                scatter_df["disp_y_min"],
            ],
            ignore_index=True,
        ),
    )
    _set_signed_limits(
        ax,
        pd.concat(
            [
                scatter_df["max_vx_base"],
                scatter_df["min_vx_base"],
                scatter_df["max_vy_base"],
                scatter_df["min_vy_base"],
            ],
            ignore_index=True,
        ),
        axis="y",
    )
    _apply_manual_limits(ax, xlim=plot_opts["xlim"], ylim=plot_opts["ylim"])
    fig.tight_layout()
    return fig, scatter_df, fit_summary


def main():
    args = _parse_args()
    db_path = _get_db_path(db_path=args.db_path, results_dir=args.results_dir)
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    length_unit, force_unit = _resolve_unit_labels(args)
    global_xlim = tuple(args.xlim) if args.xlim else None
    global_ylim = tuple(args.ylim) if args.ylim else None
    plot_opts_common = {"show_titles": not args.hide_titles}
    disp_opts = {
        **plot_opts_common,
        "xlim": tuple(args.disp_xlim) if args.disp_xlim else global_xlim,
        "ylim": tuple(args.disp_ylim) if args.disp_ylim else global_ylim,
    }
    drift_opts = {
        **plot_opts_common,
        "xlim": tuple(args.drift_xlim) if args.drift_xlim else global_xlim,
        "ylim": tuple(args.drift_ylim) if args.drift_ylim else global_ylim,
    }
    scatter_opts = {
        **plot_opts_common,
        "xlim": tuple(args.scatter_xlim) if args.scatter_xlim else global_xlim,
        "ylim": tuple(args.scatter_ylim) if args.scatter_ylim else global_ylim,
    }

    with sqlite3.connect(str(db_path)) as conn:
        _print_counts(conn)

        run_id = args.run_id or _get_latest_run_id(conn)
        if run_id is None:
            print("No hay runs en la base.")
            return

        if args.run_id is None:
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

        disp_summary = _build_node_disp_summary(df_nodes)
        drift_summary = _build_drift_summary(df_drifts)
        fig_disp = _plot_node_disp(df_nodes, length_unit, disp_opts)
        fig_drift = _plot_drifts(df_drifts, length_unit, drift_opts)
        fig_scatter, scatter_summary, fit_summary = _plot_base_shear_vs_disp(
            df_nodes, df_summary, length_unit, force_unit, scatter_opts
        )

        if args.export_dir:
            export_dir = Path(args.export_dir).resolve()
        elif args.results_dir:
            export_dir = Path(args.results_dir).resolve() / "figures"
        else:
            export_dir = db_path.parent / "figures"

        if fig_disp is not None:
            _export_figure(fig_disp, export_dir, "displacement_profiles")
        if fig_drift is not None:
            _export_figure(fig_drift, export_dir, "drift_profiles")
        if fig_scatter is not None:
            _export_figure(fig_scatter, export_dir, "base_shear_vs_displacement")
        _export_table(disp_summary, export_dir, "displacement_summary")
        _export_table(drift_summary, export_dir, "drift_summary")
        _export_table(scatter_summary, export_dir, "base_shear_summary")
        _export_table(fit_summary, export_dir, "linear_fit_summary")
        plt.show()


if __name__ == "__main__":
    main()
