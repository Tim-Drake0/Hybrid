import yaml
import os

# ---------------- CONFIG ----------------
yaml_file = "C:/Git/Hybrid/tools/buses/busDef.yaml"
arduino_sketch_dir = "C:/Git/Hybrid/tools/buses/main"
output_dir = os.path.join(arduino_sketch_dir, "src")
os.makedirs(output_dir, exist_ok=True)
# ---------------------------------------

# Load YAML
with open(yaml_file, "r") as f:
    buses = yaml.safe_load(f)
    