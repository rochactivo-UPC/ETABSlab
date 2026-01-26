from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs.nodes_config import load_nodes_config


def main():
    config_path = Path("config").resolve() / "nodes.yaml"
    case_name, model_path, nodes = load_nodes_config(config_path)
    print(case_name)
    print(model_path)
    for node in nodes:
        print(node)


if __name__ == "__main__":
    main()
