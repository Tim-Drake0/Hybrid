import serial
import struct
import yaml
import threading
from collections import deque
import time

# ---------------- CONFIG ----------------
STREAMS_YAML_FILE = "C:/Git/Hybrid/tools/buses/streamDef.yaml"
BUS_YAML_FILE = "C:/Git/Hybrid/tools/buses/busDef.yaml"
SERIAL_PORT = "COM4"
BAUD_RATE = 115200
STREAM_NAME = "streamSerialTelem"
MAX_POINTS = 500
# ---------------------------------------

# Load YAML
with open(STREAMS_YAML_FILE, "r") as f:
    streams = yaml.safe_load(f)
with open(BUS_YAML_FILE, "r") as f:
    buses = yaml.safe_load(f)

thisStream = streams[STREAM_NAME]

# Open serial
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

class Frame:
    timestamp: int = 0
    volt_batt: float = 0
    volt_3v: float = 0
    volt_5v: float = 0
    temp: float = 0
    pressure: float = 0
    humidity: float = 0
    altitude: float = 0
    accelx: float = 0
    accely: float = 0
    accelz: float = 0
    magx: float = 0
    magy: float = 0
    magz: float = 0
    gyrox: float = 0
    gyroy: float = 0
    gyroz: float = 0

latest_frame = Frame()  # module-level variable

# ---------------- HELPERS ----------------
def bytes2Volts(packet, startByte):
    raw_volts = (packet[startByte] << 8) | packet[startByte+1]
    return (raw_volts / 1024) * 3.3

def bytes2Float(packet, startByte):
    raw_bytes = bytes(packet[startByte:startByte+4])
    return struct.unpack('>f', raw_bytes)[0]

def find_and_read_packet():
    while True:
        b1 = ser.read(1)
        if len(b1) == 0 or b1[0] != (thisStream['header'] >> 8) & 0xFF:
            continue
        b2 = ser.read(1)
        if len(b2) == 0 or b2[0] != thisStream['header'] & 0xFF:
            continue
        b3 = ser.read(1)
        if len(b3) == 0 or b3[0] != (thisStream['id'] >> 8) & 0xFF:
            continue
        b4 = ser.read(1)
        if len(b4) == 0 or b4[0] != thisStream['id'] & 0xFF:
            continue

        remaining = ser.read(thisStream['size'] - 4)
        if len(remaining) != thisStream['size'] - 4:
            continue
        packet = list(b1) + list(b2) + list(b3) + list(b4) + list(remaining)
        return packet

def read_serial_loop():
    while True:
        try:
            packet = find_and_read_packet()
            latest_frame.timestamp = ((packet[4] << 24) | (packet[5] << 16) | (packet[6] << 8) | packet[7]) / 1000
            latest_frame.volt_batt = bytes2Volts(packet, 11)
            latest_frame.volt_3v = bytes2Volts(packet, 13)
            latest_frame.volt_5v = bytes2Volts(packet, 15)
            latest_frame.temp = bytes2Float(packet, 19)
            latest_frame.pressure = bytes2Float(packet, 23)/6895
            latest_frame.humidity = bytes2Float(packet, 27)
            latest_frame.altitude = bytes2Float(packet, 31)
            latest_frame.accelx = bytes2Float(packet, 37)
            latest_frame.accely = bytes2Float(packet, 37+4)
            latest_frame.accelz = bytes2Float(packet, 37+8)
            latest_frame.magx  = bytes2Float(packet, 49)
            latest_frame.magy  = bytes2Float(packet, 49+4)
            latest_frame.magz  = bytes2Float(packet, 49+8)
            latest_frame.gyrox = bytes2Float(packet, 61)
            latest_frame.gyroy = bytes2Float(packet, 61+4)
            latest_frame.gyroz = bytes2Float(packet, 61+8)
            
            
        except Exception as e:
            print("Serial read error:", e)
            time.sleep(0.01)

# Start reading in background thread
thread = threading.Thread(target=read_serial_loop, daemon=True)
thread.start()
