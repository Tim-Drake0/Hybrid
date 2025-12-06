import yaml
import os

# ---------------- CONFIG ----------------
yaml_file = "C:/Git/Hybrid/tools/bus/buses/busPwr.yaml"
output_file = "C:/Git/Hybrid/tools/bus/read_busPwr_serial.py"
COM_PORT = "COM3"       # default COM port
BAUD_RATE = 115200
# ---------------------------------------

# Load YAML
with open(yaml_file, "r") as f:
    data = yaml.safe_load(f)

# Extract fields
field_names = [k for k, v in data.items() if isinstance(v, dict)]

# Determine buffer size automatically (in bytes)
buffer_size_bits = 0
for field in field_names:
    field_info = data[field]
    buffer_size_bits = max(buffer_size_bits, field_info['offset'] + field_info['bits'])
buffer_size = (buffer_size_bits + 7) // 8  # round up to next byte
buffer_size = max(buffer_size, 4)  # at least 4 bytes for 3x10-bit fields

# Generate Python script
script = f"""import serial
import time

# -------- CONFIG --------
COM_PORT = "{COM_PORT}"
BAUD_RATE = {BAUD_RATE}
BUFFER_SIZE = {buffer_size}  # auto-computed from YAML
# ------------------------

ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
time.sleep(2)  # wait for Arduino reset

print("Listening for busPwr packets...")

# Unpack n-bit value from buffer (supports little/big endian)
def unpack_bits(buf, bit_offset, bits, endian='little'):
    val = 0
    if endian == 'little':
        byte_index = bit_offset // 8
        bit_index  = bit_offset % 8
        if byte_index < len(buf):
            val |= buf[byte_index]
        if byte_index + 1 < len(buf):
            val |= buf[byte_index + 1] << 8
        if byte_index + 2 < len(buf):
            val |= buf[byte_index + 2] << 16
        val >>= bit_index
        mask = (1 << bits) - 1
        return val & mask
    else:  # big endian
        val = 0
        for b in range(bits):
            abs_bit = bit_offset + b
            byte_index = abs_bit // 8
            bit_index = abs_bit % 8
            if byte_index < len(buf):
                bit_val = (buf[byte_index] >> (7 - bit_index)) & 1
                val |= bit_val << (bits - 1 - b)
        return val

def parse_packet(packet):
    data = {{}}
"""

# Generate parsing + calibration code for each field
for field in field_names:
    offset = data[field]['offset']
    bits   = data[field]['bits']
    endian = data[field].get('endian', 'little')
    c0     = data[field].get('c0', 0.0)
    c1     = data[field].get('c1', 1.0)
    script += f"    # {field}\n"
    script += f"    raw_{field} = unpack_bits(packet, {offset}, {bits}, endian='{endian}')\n"
    script += f"    data['{field}'] = {c0} + {c1} * raw_{field}\n\n"

script += """
    return data

try:
    while True:
        if ser.in_waiting >= BUFFER_SIZE:
            packet = ser.read(BUFFER_SIZE)
            fields = parse_packet(packet)
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # milliseconds
            print(f"[{timestamp}] ", end="")
            print(", ".join([f"{k}: {v:.2f}" for k,v in fields.items()]))
except KeyboardInterrupt:
    print("\\nExiting...")
finally:
    ser.close()
"""

# Write to file
with open(output_file, "w") as f:
    f.write(script)

print(f"Serial reader script generated at:\n{output_file}")
