import serial
import yaml
import threading
from collections import deque
import time
from pathlib import Path
import deserializeBuses as dsb


# ---------------- CONFIG ----------------
SERIAL_PORTS = ["COM2","COM3","COM4","COM5","COM6","COM7","COM8"]
BAUD_RATE = 1000000

STREAM_NAME = "streamSerialTelem"
MAX_POINTS = 500
# ---------------------------------------

repo_root = Path(__file__).resolve().parents[2]  # adjust n once
STREAMS_YAML_FILE = repo_root / "tools" / "buses" / "streamDef.yaml"
BUS_YAML_FILE = repo_root / "tools" / "buses" / "busDef.yaml"

# Load YAML
with open(STREAMS_YAML_FILE, "r") as f:
    streams = yaml.safe_load(f)
with open(BUS_YAML_FILE, "r") as f:
    buses = yaml.safe_load(f)

streamTelem = dsb.StreamTelem()  
busPwr = dsb.BusPwr()
busBME280 = dsb.BusBME280()
busLSM9DS1 = dsb.BusLSM9DS1()
busADXL375 = dsb.BusADXL375()
debug = dsb.Debug()

def find_serial():
    for port in SERIAL_PORTS:
        try:
            ser = serial.Serial(port, BAUD_RATE, timeout=1)
            return ser, port, BAUD_RATE
        except serial.SerialException:
            pass
    return None, None, None

def read_serial_loop():
    while True:
        try:
            
            streamTelem.find_and_read_packet()
            
            if streamTelem.packet== False:
                print("bad packet")
                continue
            
            idx = 4
            streamTelem.timestamp   = dsb.bytes2Num(streamTelem.packet, idx, 4); idx += 4
            streamTelem.sensorsBIT  = streamTelem.packet[idx]; idx += 1
            
            # Buses deserialize:
            busPwr.readBuffer(streamTelem.packet, idx); idx += busPwr.size
            busBME280.readBuffer(streamTelem.packet, idx); idx += busBME280.size
            busLSM9DS1.readBuffer(streamTelem.packet, idx); idx += busLSM9DS1.size
            busADXL375.readBuffer(streamTelem.packet, idx); idx += busADXL375.size
            debug.readBuffer(streamTelem.packet, idx); idx += debug.size
             
        except Exception as e:
            print("Serial read error:", e)
            time.sleep(0.01)

ser, activePort, activeRate = find_serial()

if activePort:
    # Start reading in background thread
    print(f"Found activity on {activePort} at {activeRate} baudrate")
    thread = threading.Thread(target=read_serial_loop, daemon=True)
    thread.start()
else:
    print("Serial Invalid!")