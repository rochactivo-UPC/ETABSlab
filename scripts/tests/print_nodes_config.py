from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs.nodes_config import load_nodes_config


def main():
    config_path = Path("config").resolve() / "settings.yaml"
    case_name, model_path, output_time_step, nodes, _nlth_case_config, _overwrite_db, _output_units, _accel_in_g, *_rest = load_nodes_config(config_path)
    print(case_name)
    print(model_path)
    print(output_time_step)
    for node in nodes:
        print(node)


if __name__ == "__main__":
    main()
