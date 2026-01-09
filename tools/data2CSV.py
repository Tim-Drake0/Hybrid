import struct
import csv

input_file = "DATA009.bin"
output_file = "sd_binary_log.csv"

# Struct format with padding and correct types
frame_struct = struct.Struct('<IBxHHHfffffffffffffffffffI')
frame_size = frame_struct.size
print(f"Frame size: {frame_size} bytes")

# Read frames from binary
frames = []
with open(input_file, 'rb') as f:
    while True:
        data = f.read(frame_size)
        if len(data) < frame_size:
            break
        frame = frame_struct.unpack(data)
        frames.append(frame)

# Header for CSV
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

# Conversion table: (c0, c1) for each field
# Example: battVolts needs scaling by 0.001 to get volts, etc.
# Set (c0, c1) = (0,1) for fields you don't want to scale
conversions = [
    (0, 1),    # currentMillis
    (0, 1),    # sensorsBIT
    (0, 3.3/1024),# battVolts -> volts
    (0, 3.3/1024),# voltage3V -> volts
    (0, 3.3/1024),# voltage5V -> volts
    (0, 1),    # temperatureC
    (0, 1),    # pressurePasc
    (0, 1),    # humidityRH
    (0, 1),    # altitudeM
    (0, 1),    # accelx
    (0, 1),    # accely
    (0, 1),    # accelz
    (0, 1),    # magx
    (0, 1),    # magy
    (0, 1),    # magz
    (0, 1),    # gyrox
    (0, 1),    # gyroy
    (0, 1),    # gyroz
    (0, 1),    # highG_accelx
    (0, 1),    # highG_accely
    (0, 1),    # highG_accelz
    (0, 1),    # pitch
    (0, 1),    # roll
    (0, 1),    # yaw
    (0, 1),    # loopTime
]

# Apply conversion and write CSV
with open(output_file, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(header)
    for frame in frames:
        converted = [(frame[i] * conversions[i][1] + conversions[i][0]) for i in range(len(frame))]
        writer.writerow(converted)

print(f"Parsed {len(frames)} frames to {output_file}")
