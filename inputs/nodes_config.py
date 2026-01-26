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
        raise ValueError("nodes.yaml debe incluir model_path")

    case_name = data.get("case_name")
    if not case_name:
        raise ValueError("nodes.yaml debe incluir case_name")

    nodes = data.get("nodes", [])
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("nodes.yaml debe incluir una lista no vacia de nodes")

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

    return str(case_name), str(model_path), specs
