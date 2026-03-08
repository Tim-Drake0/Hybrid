import serial
import yaml
import threading
from collections import deque
import time
from pathlib import Path
#import deserializeBuses as dsb
import struct


# ---------------- CONFIG ----------------
SERIAL_PORTS = ["COM2","COM3","COM4","COM5","COM6","COM7","COM8"]
BAUD_RATE = 2000000

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


ser = None

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
    
class BusPwr:
    timestamp:   int = 0
    id:          int = 6910
    size:        int = 14
    packetsSent: int = 0
    battVolts:   float = 1023
    voltage3V:   float = 1023
    voltage5V:   float = 1023
    voltsLSB: float = 0.00322265625

    def readBuffer(self, packet, idx):
        self.id           = bytes2Num(packet, idx, 2);    idx += 2
        self.timestamp    = bytes2Num(packet, idx, 4);    idx += 4
        self.packetsSent  = bytes2Num(packet, idx, 2);    idx += 2
        self.battVolts    = bytes2Num(packet, idx, 2) * self.voltsLSB; idx += 2
        self.voltage3V    = bytes2Num(packet, idx, 2) * self.voltsLSB; idx += 2
        self.voltage5V    = bytes2Num(packet, idx, 2) * self.voltsLSB; idx += 2

class BusBME280:
    timestamp:   int = 0
    id:          int = 6911
    size:        int = 22
    packetsSent: int = 0
    temperatureC:   float = 9999
    pressurePasc:   float = 9999
    humidityRH:   float = 9999
    altitudeM:   float = 9999

    def readBuffer(self, packet, idx):
        self.id           = bytes2Num(packet, idx, 2);    idx += 2
        self.timestamp    = bytes2Num(packet, idx, 4);    idx += 4
        self.temperatureC    = bytes2Float(packet, idx); idx += 4
        self.pressurePasc    = bytes2Float(packet, idx); idx += 4
        self.humidityRH    = bytes2Float(packet, idx); idx += 4
        self.altitudeM    = bytes2Float(packet, idx); idx += 4

class BusLSM9DS1:
    timestamp:   int = 0
    id:          int = 6912
    size:        int = 54
    packetsSent: int = 0
    accelx:   float = 9999
    accely:   float = 9999
    accelz:   float = 9999
    magx:   float = 9999
    magy:   float = 9999
    magz:   float = 9999
    gyrox:   float = 9999
    gyroy:   float = 9999
    gyroz:   float = 9999
    pitch:   float = 9999
    roll:   float = 9999
    yaw:   float = 9999

    def readBuffer(self, packet, idx):
        self.id           = bytes2Num(packet, idx, 2);    idx += 2
        self.timestamp    = bytes2Num(packet, idx, 4);    idx += 4
        self.accelx    = bytes2Float(packet, idx); idx += 4
        self.accely    = bytes2Float(packet, idx); idx += 4
        self.accelz    = bytes2Float(packet, idx); idx += 4
        self.magx    = bytes2Float(packet, idx); idx += 4
        self.magy    = bytes2Float(packet, idx); idx += 4
        self.magz    = bytes2Float(packet, idx); idx += 4
        self.gyrox    = bytes2Float(packet, idx); idx += 4
        self.gyroy    = bytes2Float(packet, idx); idx += 4
        self.gyroz    = bytes2Float(packet, idx); idx += 4
        self.pitch    = bytes2Float(packet, idx); idx += 4
        self.roll    = bytes2Float(packet, idx); idx += 4
        self.yaw    = bytes2Float(packet, idx); idx += 4

class BusADXL375:
    timestamp:   int = 0
    id:          int = 6913
    size:        int = 20
    packetsSent: int = 0
    highG_accelx:   float = 9999
    highG_accely:   float = 9999
    highG_accelz:   float = 9999

    def readBuffer(self, packet, idx):
        self.id           = bytes2Num(packet, idx, 2);    idx += 2
        self.timestamp    = bytes2Num(packet, idx, 4);    idx += 4
        self.highG_accelx    = bytes2Float(packet, idx); idx += 4
        self.highG_accely    = bytes2Float(packet, idx); idx += 4
        self.highG_accelz    = bytes2Float(packet, idx); idx += 4

class Debug:
    timestamp:   int = 0
    id:          int = 6914
    size:        int = 12
    packetsSent: int = 0
    loopTime:   int = 0

    def readBuffer(self, packet, idx):
        self.id           = bytes2Num(packet, idx, 2);    idx += 2
        self.timestamp    = bytes2Num(packet, idx, 4);    idx += 4
        self.packetsSent  = bytes2Num(packet, idx, 2);    idx += 2
        self.loopTime    = bytes2Num(packet, idx, 4); idx += 4


class StreamTelem:
    header:      int = 43962
    timestamp:   int = 0
    id:          int = 6900
    size:        int = 78
    packetsSent: int = 0
    packet:      int = [0] * size
    sensorsBIT:  int = 0
    
    def readBuffer(self):
        
        idx = 2
        self.id           = bytes2Num(self.packet, idx, 2);    idx += 2
        self.size         = self.packet[idx]; idx += 1
        self.timestamp    = bytes2Num(self.packet, idx, 4);    idx += 4
        self.sensorsBIT  = self.packet[idx]; idx += 1
        
        # BME280
        busBME280.temperatureC    = bytes2Float(self.packet, idx); idx += 4
        busBME280.pressurePasc    = bytes2Float(self.packet, idx); idx += 4
        busBME280.humidityRH    = bytes2Float(self.packet, idx); idx += 4
        busBME280.altitudeM    = bytes2Float(self.packet, idx); idx += 4
        
        # LSM9DS1
        busLSM9DS1.accelx    = bytes2Float(self.packet, idx); idx += 4
        busLSM9DS1.accely    = bytes2Float(self.packet, idx); idx += 4
        busLSM9DS1.accelz    = bytes2Float(self.packet, idx); idx += 4
        busLSM9DS1.magx    = bytes2Float(self.packet, idx); idx += 4
        busLSM9DS1.magy    = bytes2Float(self.packet, idx); idx += 4
        busLSM9DS1.magz    = bytes2Float(self.packet, idx); idx += 4
        busLSM9DS1.gyrox    = bytes2Float(self.packet, idx); idx += 4
        busLSM9DS1.gyroy    = bytes2Float(self.packet, idx); idx += 4
        busLSM9DS1.gyroz    = bytes2Float(self.packet, idx); idx += 4
        busLSM9DS1.pitch    = bytes2Float(self.packet, idx); idx += 4
        busLSM9DS1.roll    = bytes2Float(self.packet, idx); idx += 4
        busLSM9DS1.yaw    = bytes2Float(self.packet, idx); idx += 4

        # Debug
        debug.loopTime = bytes2Num(self.packet, idx, 4); idx += 4

    def find_and_read_packet(self, ser):
        # maybe add timeout to this>
        while True:
            thisPacket = ser.read(self.size)
            
            if len(thisPacket) != self.size:
                print("Dumped packet, wrong size ", len(thisPacket), self.size)
                continue
            
            if (thisPacket[0] != (self.header >> 8) & 0xFF or thisPacket[1] != self.header & 0xFF):
                print(f'ERROR: Header is incorrect: {int.from_bytes(thisPacket[:2], "big"):#06x} ({int.from_bytes(thisPacket[:2], "big")}). Expected {self.header} ({self.header:#06x})')
            
            if (thisPacket[2] != (self.id >> 8) & 0xFF or thisPacket[3] != self.id & 0xFF):
                print(f'ERROR: ID is incorrect: {int.from_bytes(thisPacket[2:4], "big")} ({int.from_bytes(thisPacket[2:4], "big"):#06x}). Expected {self.id} ({self.id:#06x})')
                continue
            
            self.packet = thisPacket
            return
        
    
streamTelem = StreamTelem()  
busPwr = BusPwr()
busBME280 = BusBME280()
busLSM9DS1 = BusLSM9DS1()
busADXL375 = BusADXL375()
debug = Debug()           


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
            
            streamTelem.find_and_read_packet(ser)
            
            if streamTelem.packet== False:
                print("bad packet")
                continue
            
            streamTelem.readBuffer()
             
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