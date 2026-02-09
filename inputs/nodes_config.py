from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class NodeSpec:
    name: str
    joint: str
    z: float


def load_nodes_config(path: str):
    config_path = Path(path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(config_path)

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    model_path = data.get("model_path")
    if not model_path:
        raise ValueError("settings.yaml debe incluir model_path")

    case_name = data.get("case_name")
    if not case_name:
        raise ValueError("settings.yaml debe incluir case_name")

    output_time_step = float(data.get("output_time_step", 0.05))
    overwrite_db = bool(data.get("overwrite_db", False))
    output_units = data.get("output_units", "cm")
    accel_in_g = bool(data.get("accel_in_g", True))

    nlth_case = data.get("nlth_case", {})
    if nlth_case is None:
        nlth_case = {}
    if not isinstance(nlth_case, dict):
        raise ValueError("settings.yaml: nlth_case debe ser un dict")

    nlth_case_config = {
        "apply_parameters": bool(nlth_case.get("apply_parameters", True)),
        "p_delta": bool(nlth_case.get("p_delta", True)),
        "damping": nlth_case.get("damping"),
        "time_integration": nlth_case.get("time_integration"),
        "nonlinear_parameters": nlth_case.get("nonlinear_parameters"),
        "initial_conditions": nlth_case.get("initial_conditions"),
        "initial_case": nlth_case.get("initial_case", "NL DL+0.25LL"),
    }

    use_ping_pong = bool(data.get("use_ping_pong", False))
    ping_pong_cases = data.get("ping_pong_cases", ["NLTH_A", "NLTH_B"])
    if not isinstance(ping_pong_cases, list) or len(ping_pong_cases) != 2:
        raise ValueError("settings.yaml: ping_pong_cases debe ser lista de 2 nombres")

    checkpoint_every = int(data.get("checkpoint_every", 10))
    clear_results_after_edp = bool(data.get("clear_results_after_edp", False))
    initial_gravity_case = str(data.get("initial_gravity_case", "NL DL+0.25LL"))
    energy_link = data.get("energy_link", "")
    energy_component = data.get("energy_component", "U1_P")
    energy_point_elm = data.get("energy_point_elm", "I-End")
    energy_mode = str(data.get("energy_mode", "signed"))
    if energy_link is None:
        energy_link = ""

    nodes = data.get("nodes", [])
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("settings.yaml debe incluir una lista no vacia de nodes")

    specs = []
    seen_names = set()
    for entry in nodes:
        if not isinstance(entry, dict):
            raise ValueError("Cada node debe ser un dict con name, joint y z")
        name = str(entry.get("name", "")).strip()
        joint = str(entry.get("joint", "")).strip()
        if not name or not joint:
            raise ValueError("Cada node debe tener name y joint validos")
        if name in seen_names:
            raise ValueError(f"Nombre de node duplicado: {name}")
        seen_names.add(name)
        if "z" not in entry:
            raise ValueError(f"Node sin z: {name}")
        specs.append(NodeSpec(name=name, joint=joint, z=float(entry["z"])))

    return (
        str(case_name),
        str(model_path),
        output_time_step,
        specs,
        nlth_case_config,
        overwrite_db,
        output_units,
        accel_in_g,
        use_ping_pong,
        ping_pong_cases,
        checkpoint_every,
        clear_results_after_edp,
        initial_gravity_case,
        str(energy_link),
        str(energy_component),
        str(energy_point_elm),
        str(energy_mode),
    )
