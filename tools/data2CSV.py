import struct
import csv

input_file = "TEST.bin"
output_file = "sd_binary_log.csv"

# Struct format with padding and correct types
frame_struct = struct.Struct('<IBxHHHfffffffffffffffffffI')
frame_size = frame_struct.size
print(f"Frame size: {frame_size} bytes")

frames = []
with open(input_file, 'rb') as f:
    while True:
        data = f.read(frame_size)
        if len(data) < frame_size:
            break
        frame = frame_struct.unpack(data)
        frames.append(frame)

header = [
    "currentMillis", "sensorsBIT",
    "battVolts", "voltage3V", "voltage5V",
    "temperatureC", "pressurePasc", "humidityRH", "altitudeM",
    "accelx", "accely", "accelz",
    "magx", "magy", "magz",
    "gyrox", "gyroy", "gyroz",
    "highG_accelx", "highG_accely", "highG_accelz",
    "pitch", "roll", "yaw",
    "loopTime"
]

with open(output_file, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(header)
    for frame in frames:
        writer.writerow(frame)

print(f"Parsed {len(frames)} frames to {output_file}")
