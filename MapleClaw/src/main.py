from pathlib import Path
import yaml

global_config_path = Path(__file__).resolve().parent / "config" / "global_config.yaml"

with open(file=global_config_path, mode='r', encoding='utf-8') as file:
    config = yaml.safe_load(file)
print(config.get("model"))