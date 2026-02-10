from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs.nodes_config import load_nodes_config
from solvers.sap2000.connect import get_sap2000_model
from solvers.sap2000.model_checks import check_model_loaded_and_unlocked
from solvers.sap2000.results_setup import select_case_for_output
from solvers.sap2000.edp_energy import (
    get_link_energy,
    get_link_force_deformation,
    dump_link_force_raw,
)


def _summarize_link_force(sap_model, link_name, item_type):
    result = sap_model.Results.LinkForce(
        link_name,
        item_type,
        0,
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    if not isinstance(result, (tuple, list)) or len(result) < 2:
        return None, None
    if isinstance(result[-1], int):
        ret = result[-1]
        number_results = result[0] if len(result) > 0 else None
    else:
        ret = result[0]
        number_results = result[1] if len(result) > 1 else None
    return ret, number_results


def _summarize_link_deformation(sap_model, link_name, item_type):
    result = sap_model.Results.LinkDeformation(
        link_name,
        item_type,
        0,
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    if not isinstance(result, (tuple, list)) or len(result) < 2:
        return None, None
    if isinstance(result[-1], int):
        ret = result[-1]
        number_results = result[0] if len(result) > 0 else None
    else:
        ret = result[0]
        number_results = result[1] if len(result) > 1 else None
    return ret, number_results


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


def main():
    base_dir = Path(__file__).resolve().parents[1]
    config_path = base_dir / "config" / "settings.yaml"
    (
        _case_name_cfg,
        model_path,
        _output_time_step,
        _nodes,
        _nlth_case_config,
        _overwrite_db,
        _output_units,
        _accel_in_g,
        use_ping_pong,
        ping_pong_cases,
        _checkpoint_every,
        _clear_results_after_edp,
        _initial_gravity_case,
        energy_link,
        enable_link_energy,
        energy_component,
        energy_point_elm,
        _energy_mode,
    ) = load_nodes_config(config_path)

    if not enable_link_energy:
        print("[energy] enable_link_energy=false: se omite lectura de resultados de link.")
        return

    if not energy_link:
        raise RuntimeError("energy_link vacio en settings.yaml")

    sap_model = get_sap2000_model()
    if model_path:
        sap_model.File.OpenFile(str(Path(model_path).resolve()))
    check_model_loaded_and_unlocked(sap_model, model_path, allow_locked=True)

    try:
        result = sap_model.LinkObj.GetNameList()
        if isinstance(result, (tuple, list)) and len(result) >= 3:
            ret, _count, names = result[0], result[1], result[2]
            if ret == 0 and isinstance(names, (list, tuple)):
                if energy_link not in set(names):
                    print(
                        f"[energy] Link {energy_link} no esta en el modelo. "
                        f"Ejemplos: {list(names)[:5]}"
                    )
    except Exception:
        pass

    if use_ping_pong:
        cases = ["NLTH_C"]
    else:
        cases = [_case_name_cfg]
    energy_links = ["4"]
    results_dir = base_dir / "results"
    for case_name in cases:
        print(f"[energy] Caso: {case_name} | Links: {', '.join(energy_links)} | Comp: {energy_component}")
        select_case_for_output(sap_model, case_name)
        total_energy = None
        total_steps = None

        for link_id in energy_links:
            raw = dump_link_force_raw(sap_model, link_id)
            if raw.get("ret") == 0:
                out_raw = results_dir / f"link_force_raw_{case_name}_{link_id}.csv"
                _write_link_force_raw_csv(out_raw, raw)
                print(f"[energy] Raw CSV: {out_raw}")
            else:
                print(f"[energy] LinkForce raw sin datos ({link_id}): {raw.get('tries')}")
            for item_type in (0, 1, 2):
                ret_f, n_f = _summarize_link_force(sap_model, link_id, item_type)
                ret_d, n_d = _summarize_link_deformation(sap_model, link_id, item_type)
                print(
                    f"[energy] Link {link_id} ItemType={item_type} "
                    f"LinkForce ret={ret_f} n={n_f} | LinkDeformation ret={ret_d} n={n_d}"
                )

            energy = get_link_energy(
                sap_model,
                link_id,
                energy_component,
                energy_point_elm,
                energy_mode="signed",
                include_history=True,
            )
            if not energy or "energy" not in energy:
                print(f"[energy] Sin resultados para {case_name} link {link_id}")
                continue
            out_csv = results_dir / f"link_energy_{case_name}_{link_id}.csv"
            _write_energy_csv(out_csv, energy.get("step_num", []), energy["energy"])
            print(f"[energy] CSV: {out_csv}")

            steps = energy.get("step_num", [])
            vals = energy.get("energy", [])
            if total_energy is None:
                total_steps = list(steps)
                total_energy = list(vals)
            else:
                n = min(len(total_energy), len(vals))
                total_energy = [total_energy[i] + vals[i] for i in range(n)]
                total_steps = total_steps[:n] if total_steps else total_steps

            try:
                hist = get_link_force_deformation(
                    sap_model,
                    link_id,
                    energy_component,
                    energy_point_elm,
                )
                disp_vals = hist.get("disp", [])
                force_vals = hist.get("force", [])
                if disp_vals and force_vals:
                    out_hys = results_dir / f"link_hysteresis_{case_name}_{link_id}.csv"
                    _write_hysteresis_csv(out_hys, disp_vals, force_vals)
                    print(f"[energy] Hysteresis CSV: {out_hys}")
            except Exception as exc:
                print(f"[energy] Histeresis omitida ({link_id}): {exc}")

        if total_energy is not None:
            out_total = results_dir / f"link_energy_{case_name}_TOTAL.csv"
            _write_energy_csv(out_total, total_steps or [], total_energy)
            print(f"[energy] TOTAL CSV: {out_total}")

    try:
        import matplotlib.pyplot as plt

        # Energy history plot (per link and total)
        for case_name in cases:
            for link_id in energy_links + ["TOTAL"]:
                csv_path = results_dir / f"link_energy_{case_name}_{link_id}.csv"
                if not csv_path.exists():
                    continue
                steps = []
                times = []
                vals = []
                with csv_path.open("r", encoding="utf-8") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        steps.append(float(row["step_num"]))
                        if "time" in row and row["time"] != "":
                            times.append(float(row["time"]))
                        vals.append(float(row["energy"]))
                if not steps:
                    continue
                x_vals = times if times else steps
                plt.figure()
                plt.plot(x_vals, vals, label=f"{case_name}-{link_id}")
                plt.xlabel("Time")
                plt.ylabel("Energy")
                plt.title(f"Energy {case_name} Link {link_id} ({energy_component})")
                plt.legend()
                out_png = results_dir / f"link_energy_{case_name}_{link_id}.png"
                plt.savefig(out_png, dpi=150)
                print(f"[energy] PNG: {out_png}")

        # Hysteresis plots
        for case_name in cases:
            for link_id in energy_links:
                csv_path = results_dir / f"link_hysteresis_{case_name}_{link_id}.csv"
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
                plt.title(f"Link {link_id} Hysteresis ({case_name}, {energy_component})")
                out_png = results_dir / f"link_hysteresis_{case_name}_{link_id}.png"
                plt.savefig(out_png, dpi=150)
                print(f"[energy] Hysteresis PNG: {out_png}")
    except Exception as exc:
        print(f"[energy] Plot omitido: {exc}")


if __name__ == "__main__":
    main()
