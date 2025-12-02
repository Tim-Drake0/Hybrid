import yaml
import os

# ---------------- CONFIG ----------------
yaml_file = "C:/Git/Hybrid/tools/bus/buses/busPwr.yaml"
arduino_sketch_dir = "C:/Git/Hybrid/tools/bus/buses/main"
output_dir = os.path.join(arduino_sketch_dir, "src")
os.makedirs(output_dir, exist_ok=True)
# ---------------------------------------

# Load YAML
with open(yaml_file, "r") as f:
    data = yaml.safe_load(f)

# Extract fields (skip name/id/freq)
field_names = [k for k, v in data.items() if isinstance(v, dict)]
frequency = data.get("freq", 1)

# -------- busPwr.h --------
header_path = os.path.join(output_dir, "busPwr.h")
header = f"""#ifndef BUSPWR_H
#define BUSPWR_H

#include <Arduino.h>

struct FieldConfig {{
    int bits;
    int offset;
    const char* endian;
    double c0;
    double c1;
}};

struct BusPwrConfig {{
    const char* name;
    int id;
    unsigned int frequency; // Hz
"""

for field in field_names:
    header += f"    FieldConfig {field};\n"

header += """

    const FieldConfig* getField(const char* fieldName) const;
    void serialize(uint8_t* buffer, const uint16_t* values) const;
    int bufferSize() const;
};

extern const BusPwrConfig busPwr;

#endif
"""

with open(header_path, "w") as f:
    f.write(header.strip())

# -------- busPwr.cpp --------
cpp_path = os.path.join(output_dir, "busPwr.cpp")
cpp = '#include "busPwr.h"\n#include <string.h>\n#include <string.h>\n\n'

# Struct initialization
cpp += "const BusPwrConfig busPwr = {\n"
cpp += f'    "{data["name"]}",\n'
cpp += f'    {data["id"]},\n'
cpp += f'    {frequency},\n'

for i, field in enumerate(field_names):
    fld = data[field]
    c0 = fld.get("c0", 0.0)
    c1 = fld.get("c1", 1.0)
    cpp += f'    {{ {fld["bits"]}, {fld["offset"]}, "{fld.get("endian","little")}", {c0}, {c1} }}'
    cpp += "," if i < len(field_names) - 1 else ""
    cpp += "\n"

cpp += "};\n\n"

# getField function
cpp += "const FieldConfig* BusPwrConfig::getField(const char* fieldName) const {\n"
for field in field_names:
    cpp += f'    if (strcmp(fieldName, "{field}") == 0) return &{field};\n'
cpp += "    return nullptr;\n}\n\n"

# bufferSize function
cpp += "int BusPwrConfig::bufferSize() const {\n"
cpp += "    int size = 0;\n"
for field in field_names:
    cpp += f"    size = ((({field}.offset + {field}.bits + 7) / 8) > size) ? (({field}.offset + {field}.bits + 7) / 8) : size;\n"
cpp += "    return size;\n}\n\n"

# serialize function with endian support
cpp += "void BusPwrConfig::serialize(uint8_t* buffer, const uint16_t* values) const {\n"
cpp += "    memset(buffer, 0, bufferSize());\n\n"

for idx, field in enumerate(field_names):
    fld = data[field]
    bits = fld['bits']
    cpp += f"    // {field}\n"
    cpp += "    {\n"
    cpp += f"        uint16_t val = values[{idx}] & ((1 << {bits}) - 1);\n"
    cpp += f"        int bitOffset = {field}.offset;\n"
    cpp += f"        if (strcmp({field}.endian, \"little\") == 0) {{\n"
    cpp += "            int byteIndex = bitOffset / 8;\n"
    cpp += "            int bitIndex  = bitOffset % 8;\n"
    cpp += f"            buffer[byteIndex]     |= (val << bitIndex) & 0xFF;\n"
    cpp += f"            buffer[byteIndex + 1] |= (val >> (8 - bitIndex)) & 0xFF;\n"
    cpp += f"            if (bitIndex + {bits} > 8) buffer[byteIndex + 2] |= (val >> (16 - bitIndex)) & 0xFF;\n"
    cpp += "        } else { // big endian\n"
    cpp += f"            for (int b = 0; b < {bits}; ++b) {{\n"
    cpp += f"                int bitVal = (val >> ({bits} - 1 - b)) & 1;\n"
    cpp += "                int absBit = bitOffset + b;\n"
    cpp += "                buffer[absBit / 8] |= bitVal << (7 - (absBit % 8));\n"
    cpp += "            }\n"
    cpp += "        }\n"
    cpp += "    }\n\n"

cpp += "}\n"

with open(cpp_path, "w") as f:
    f.write(cpp)

print(f"Generated files in Arduino sketch folder:\n- {header_path}\n- {cpp_path}")
