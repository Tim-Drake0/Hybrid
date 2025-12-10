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
BAUD_RATE = 1000000
STREAM_NAME = "streamSerialTelem"
MAX_POINTS = 500
# ---------------------------------------

# Load YAML
with open(STREAMS_YAML_FILE, "r") as f:
    streams = yaml.safe_load(f)
with open(BUS_YAML_FILE, "r") as f:
    buses = yaml.safe_load(f)

thisStream = streams[STREAM_NAME]

busIDs = [6910,6911,6912,6913]

# Open serial
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

class BusPwr:
    timestamp: int = 0
    id: int = 0
    packetsSent: int = 0
    battVolts: float = 0
    voltage3V: float = 0
    voltage5V: float = 0
class BusBME280:
    timestamp: int = 0
    id: int = 0
    packetsSent: int = 0
    temperatureC: float = 0
    pressurePasc: float = 0
    humidityRH: float = 0
    altitudeM: float = 0
class BusLSM9DS1:
    timestamp: int = 0
    id: int = 0
    packetsSent: int = 0
    accelx: float = 0
    accely: float = 0
    accelz: float = 0
    magx: float = 0
    magy: float = 0
    magz: float = 0
    gyrox: float = 0
    gyroy: float = 0
    gyroz: float = 0
class BusADXL375:
    timestamp: int = 0
    id: int = 0
    packetsSent: int = 0
    highG_accelx: float = 0
    highG_accely: float = 0
    highG_accelz: float = 0

busPwr = BusPwr()
busBME280 = BusBME280()
busLSM9DS1 = BusLSM9DS1()
busADXL375 = BusADXL375()

# ---------------- HELPERS ----------------
def bytes2Num(packet, startByte, bytes):
    if bytes == 2:
        return (packet[startByte] << 8) | packet[startByte+1]
    if bytes == 4:
        return (packet[startByte] << 24) | (packet[startByte+1] << 16) | (packet[startByte+2] << 8) | packet[startByte+3]
    
def bytes2Volts(packet, startByte):
    raw_volts = (packet[startByte] << 8) | packet[startByte+1]
    return (raw_volts / 1024) * 3.3

def bytes2Float(packet, startByte):
    raw_bytes = bytes(packet[startByte:startByte+4])
    return struct.unpack('>f', raw_bytes)[0]

def find_and_read_packet(id, size):
    while True:
        b3 = ser.read(1)
        if len(b3) == 0 or b3[0] != (id >> 8) & 0xFF:
            continue
        b4 = ser.read(1)
        if len(b4) == 0 or b4[0] != id & 0xFF:
            continue

        remaining = ser.read(size - 2)
        if len(remaining) != size - 2:
            continue
        packet = list(b3) + list(b4) + list(remaining)
        return packet

def read_serial_loop():
    while True:
        try:
            for id in busIDs:
                
                if id == 6910:
                    packet = find_and_read_packet(id, 14)
                    idx = 0
                    busPwr.id   = bytes2Num(packet, idx, 2); idx += 2
                    busPwr.timestamp = ((packet[idx] << 24) | (packet[idx+1] << 16) | (packet[idx+2] << 8) | packet[idx+3]) / 1000; idx += 4
                    busPwr.packetsSent = bytes2Num(packet, idx, 2); idx += 2  
                    busPwr.battVolts = bytes2Volts(packet, idx);    idx += 2
                    busPwr.voltage3V = bytes2Volts(packet, idx);    idx += 2
                    busPwr.voltage5V = bytes2Volts(packet, idx);    idx += 2  
                    continue                 
                
                if id == 6911:   
                    packet = find_and_read_packet(id, 24)
                    idx = 0
                    busBME280.id   = bytes2Num(packet, idx, 2); idx += 2
                    busBME280.timestamp = ((packet[idx] << 24) | (packet[idx+1] << 16) | (packet[idx+2] << 8) | packet[idx+3]) / 1000; idx += 4
                    busBME280.packetsSent = bytes2Num(packet, idx, 2); idx += 2  
                    busBME280.temperatureC = bytes2Float(packet, idx);               idx += 4
                    busBME280.pressurePasc = bytes2Float(packet, idx)/6895;      idx += 4
                    busBME280.humidityRH = bytes2Float(packet, idx);           idx += 4
                    busBME280.altitudeM = bytes2Float(packet, idx);           idx += 4 
                    continue
                    
                if id == 6912: # for busLSM9DS1:
                    packet = find_and_read_packet(id, 44)
                    idx = 0
                    busLSM9DS1.id   = bytes2Num(packet, idx, 2); idx += 2
                    busLSM9DS1.timestamp = ((packet[idx] << 24) | (packet[idx+1] << 16) | (packet[idx+2] << 8) | packet[idx+3]) / 1000; idx += 4
                    busLSM9DS1.packetsSent = bytes2Num(packet, idx, 2); idx += 2  
                    busLSM9DS1.accelx = bytes2Float(packet, idx); idx += 4
                    busLSM9DS1.accely = bytes2Float(packet, idx); idx += 4
                    busLSM9DS1.accelz = bytes2Float(packet, idx); idx += 4
                    busLSM9DS1.magx   = bytes2Float(packet, idx); idx += 4
                    busLSM9DS1.magy   = bytes2Float(packet, idx); idx += 4
                    busLSM9DS1.magz   = bytes2Float(packet, idx); idx += 4
                    busLSM9DS1.gyrox  = bytes2Float(packet, idx); idx += 4
                    busLSM9DS1.gyroy  = bytes2Float(packet, idx); idx += 4
                    busLSM9DS1.gyroz  = bytes2Float(packet, idx); idx += 4
                    continue
                
                if id == 6913:
                    packet = find_and_read_packet(id, 20)
                    idx = 0
                    busADXL375.id   = bytes2Num(packet, idx, 2); idx += 2
                    busADXL375.timestamp = ((packet[idx] << 24) | (packet[idx+1] << 16) | (packet[idx+2] << 8) | packet[idx+3]) / 1000; idx += 4
                    busADXL375.packetsSent = bytes2Num(packet, idx, 2); idx += 2  
                    busADXL375.highG_accelx = bytes2Float(packet, idx);       idx += 4
                    busADXL375.highG_accely = bytes2Float(packet, idx);       idx += 4
                    busADXL375.highG_accelz = bytes2Float(packet, idx); 
             
        except Exception as e:
            print("Serial read error:", e)
            time.sleep(0.01)

# Start reading in background thread
thread = threading.Thread(target=read_serial_loop, daemon=True)
thread.start()
