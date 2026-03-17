from pathlib import Path
import argparse
import csv
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs.nodes_config import load_nodes_config
from solvers.sap2000.connect import get_sap2000_model
from solvers.sap2000.model_checks import check_model_loaded_and_unlocked
from solvers.sap2000.results_setup import select_case_for_output
from solvers.sap2000.edp_energy import (
    dump_link_force_raw,
    get_link_energy,
    get_link_force_deformation,
)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Postproceso de energia de link desde resultados de SAP2000."
    )
    parser.add_argument(
        "--settings",
        default=str((ROOT / "config" / "settings.yaml").resolve()),
        help="Ruta al settings.yaml",
    )
    parser.add_argument(
        "--results-dir",
        default=None,
        help="Carpeta de resultados donde esta edp.sqlite.",
    )
    parser.add_argument(
        "--case",
        dest="case_name",
        default=None,
        help="Caso especifico a postprocesar. Si no se indica, usa los runs terminados del SQLite.",
    )
    return parser.parse_args()


def _write_energy_csv(path: Path, step_num, energy):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["step_num", "time", "energy"])
        for s, e in zip(step_num, energy):
            writer.writerow([s, s, e])


def _write_hysteresis_csv(path: Path, disp_vals, force_vals):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["disp", "force"])
        for d, f in zip(disp_vals, force_vals):
            writer.writerow([d, f])


def _write_link_force_raw_csv(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = [
        "point_elm",
        "load_case",
        "step_type",
        "step_num",
        "time",
        "p",
        "v2",
        "v3",
        "t",
        "m2",
        "m3",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(keys)
        step_num = payload.get("step_num", [])
        values = {
            "point_elm": payload.get("point_elm", []),
            "load_case": payload.get("load_case", []),
            "step_type": payload.get("step_type", []),
            "step_num": step_num,
            "time": list(step_num) if step_num is not None else [],
            "p": payload.get("p", []),
            "v2": payload.get("v2", []),
            "v3": payload.get("v3", []),
            "t": payload.get("t", []),
            "m2": payload.get("m2", []),
            "m3": payload.get("m3", []),
        }
        rows = zip(*[values.get(k, []) for k in keys])
        for row in rows:
            writer.writerow(row)


def _resolve_results_dir(settings_path: Path, raw_results_dir: str | None) -> Path:
    if raw_results_dir:
        return Path(raw_results_dir).resolve()
    settings_root = settings_path.parent.resolve()
    if settings_root.name.lower() == "config":
        project_root = settings_root.parent
    else:
        project_root = settings_root
    return project_root / "results"


def _load_cases_from_db(db_path: Path) -> list[str]:
    if not db_path.exists():
        return []
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT case_name
            FROM runs
            WHERE finished = 1 AND COALESCE(error, '') = ''
            ORDER BY run_id
            """
        ).fetchall()
    return [str(row[0]).strip() for row in rows if row and str(row[0]).strip()]


def _plot_outputs(results_dir: Path, cases: list[str], energy_link: str, energy_component: str):
    import matplotlib.pyplot as plt

    for case_name in cases:
        for link_id in [energy_link, "TOTAL"]:
            csv_path = results_dir / f"link_energy_{case_name}_{link_id}.csv"
            if not csv_path.exists():
                continue
            steps = []
            vals = []
            with csv_path.open("r", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    steps.append(float(row["step_num"]))
                    vals.append(float(row["energy"]))
            if not steps:
                continue
            plt.figure()
            plt.plot(steps, vals, label=f"{case_name}-{link_id}")
            plt.xlabel("Step")
            plt.ylabel("Energia acumulada")
            plt.title(f"Energia {case_name} Link {link_id} ({energy_component})")
            plt.legend()
            out_png = results_dir / f"link_energy_{case_name}_{link_id}.png"
            plt.savefig(out_png, dpi=150)
            print(f"[energy] PNG: {out_png}")

        csv_path = results_dir / f"link_hysteresis_{case_name}_{energy_link}.csv"
        if not csv_path.exists():
            continue
        disp = []
        force = []
        with csv_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                disp.append(float(row["disp"]))
                force.append(float(row["force"]))
        if not disp:
            continue
        plt.figure()
        plt.plot(disp, force, linewidth=1.0)
        plt.xlabel("Disp")
        plt.ylabel("Force")
        plt.title(f"Link {energy_link} Histeresis ({case_name}, {energy_component})")
        out_png = results_dir / f"link_hysteresis_{case_name}_{energy_link}.png"
        plt.savefig(out_png, dpi=150)
        print(f"[energy] Hysteresis PNG: {out_png}")

    plt.show()


def main():
    args = _parse_args()
    settings_path = Path(args.settings).resolve()
    (
        case_name_cfg,
        model_path,
        _output_time_step,
        _nodes,
        _nlth_case_config,
        _overwrite_db,
        _output_units,
        _accel_in_g,
        _use_ping_pong,
        _ping_pong_cases,
        _use_chain_series,
        _chain_case_prefix,
        _checkpoint_every,
        _clear_results_after_edp,
        _initial_gravity_case,
        energy_link,
        enable_link_energy,
        energy_component,
        energy_point_elm,
        energy_mode,
    ) = load_nodes_config(str(settings_path))

    if not enable_link_energy:
        print("[energy] enable_link_energy=false: se omite postproceso.")
        return
    if not energy_link:
        raise RuntimeError("energy_link vacio en settings.yaml")

    results_dir = _resolve_results_dir(settings_path, args.results_dir)
    db_path = results_dir / "edp.sqlite"
    if args.case_name:
        cases = [str(args.case_name).strip()]
    else:
        cases = _load_cases_from_db(db_path)
        if not cases:
            cases = [case_name_cfg]
    print(f"[energy] Casos a postprocesar: {', '.join(cases)}")

    sap_model = get_sap2000_model()
    if model_path:
        ret = sap_model.File.OpenFile(str(Path(model_path).resolve()))
        if ret != 0:
            raise RuntimeError(f"No se pudo abrir el modelo SAP2000: {model_path}")
    check_model_loaded_and_unlocked(sap_model, model_path, allow_locked=True)

    for case_name in cases:
        print(f"[energy] Caso: {case_name} | Link: {energy_link} | Comp: {energy_component}")
        select_case_for_output(sap_model, case_name)

        raw = dump_link_force_raw(sap_model, energy_link)
        if raw.get("ret") == 0:
            out_raw = results_dir / f"link_force_raw_{case_name}_{energy_link}.csv"
            _write_link_force_raw_csv(out_raw, raw)
            print(f"[energy] Raw CSV: {out_raw}")

        energy = get_link_energy(
            sap_model,
            energy_link,
            energy_component,
            energy_point_elm,
            energy_mode=energy_mode,
            include_history=True,
        )
        if not energy or "energy" not in energy:
            print(f"[energy] Sin resultados para {case_name} link {energy_link}")
            continue

        out_csv = results_dir / f"link_energy_{case_name}_{energy_link}.csv"
        _write_energy_csv(out_csv, energy.get("step_num", []), energy["energy"])
        print(f"[energy] CSV: {out_csv}")

        out_total = results_dir / f"link_energy_{case_name}_TOTAL.csv"
        _write_energy_csv(out_total, energy.get("step_num", []), energy["energy"])
        print(f"[energy] TOTAL CSV: {out_total}")

        hist = get_link_force_deformation(
            sap_model,
            energy_link,
            energy_component,
            energy_point_elm,
        )
        disp_vals = hist.get("disp", [])
        force_vals = hist.get("force", [])
        if disp_vals and force_vals:
            out_hys = results_dir / f"link_hysteresis_{case_name}_{energy_link}.csv"
            _write_hysteresis_csv(out_hys, disp_vals, force_vals)
            print(f"[energy] Hysteresis CSV: {out_hys}")

    _plot_outputs(results_dir, cases, energy_link, energy_component)


if __name__ == "__main__":
    main()
