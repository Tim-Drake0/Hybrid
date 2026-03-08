import serial
import yaml
import threading
from collections import deque
import time
from pathlib import Path
import struct
import serial_writer as sw 
import queue

import sys
from pathlib import Path
sensor_path = Path(__file__).parent / "Sensor Info"
sys.path.append(str(sensor_path))
import INFO_BME280 as bme280
import INFO_LSM9DS1 as lsm9ds1
import INFO_EEPROM as eeprom

# ---------------- CONFIG ----------------
SERIAL_PORT = "COM5"#["COM2","COM3","COM4","COM5","COM6","COM7","COM8"]
BAUD_RATE = 9600

STREAM_NAME = "streamSerialTelem"
MAX_POINTS = 500

TELEM_HEADER = (0xAB, 0xCD)
CMD_HEADER   = (0xDE, 0xAD)
FRAME_END    = (0xEF, 0xBE)
# ---------------------------------------

ser = None
telem_queue = queue.Queue()
cmd_queue = queue.Queue()

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
  
def read_sync(ser):
    """Read until we find a known 2-byte header, return which one it was."""
    b0 = ser.read(1)
    if not b0:
        return None
    b0 = b0[0]
    while True:
        b1 = ser.read(1)
        if not b1:
            return None
        b1 = b1[0]
        pair = (b0, b1)
        if pair == TELEM_HEADER:
            return 'TELEM'
        if pair == CMD_HEADER:
            return 'CMD'
        b0 = b1  # slide the window
          
class StreamTelem:
    header:      int = 43962
    timestamp:   int = 0
    states:      int = 0
    loadCell:    float = 0
    PT_tank:    float = 0
    battVolts:    float = 0
    RSSI:    float = 0
    
    
    def readBuffer(self):
        import struct
        (self.timestamp, 
        self.states,
        self.loadCell, 
        self.PT_tank, 
        self.battVolts,
        self.RSSI) = struct.unpack_from("<IB3fH", bytes(self.packet))


    
streamTelem = StreamTelem()     


def find_serial():
    try:
        ser = serial.Serial(
            SERIAL_PORT,
            BAUD_RATE,
            timeout=1,
            xonxoff=False,    # disable software flow control
            rtscts=False,     # disable hardware flow control
            dsrdtr=False      # disable DSR/DTR flow control
        )
        return ser, SERIAL_PORT, BAUD_RATE
    except serial.SerialException:
        pass
    return None, None, None

def read_serial_loop():
    while True:
        try:
            pkt_type = read_sync(ser)
            if pkt_type is None:
                continue

            header = ser.read(2)
            if len(header) < 2:
                print(f"[TELEM] Header too short: {header.hex()}")
                continue
            resp_id = header[0]
            length  = header[1]
            payload = ser.read(length) if length > 0 else b""
            crc_b   = ser.read(1)
            end_b   = ser.read(1)
            
            if len(payload) != length:
                print(f"[TELEM] Dropped packet. Incorrect length {len(payload)}, {length}")
                
            if not end_b:
                print("[ROUTER] No frame end, re-syncing...")
                ser.read(4)
                continue
            
            if end_b[0] != FRAME_END[0]:
                print(f"[ROUTER] Bad frame end: {end_b.hex()}, re-syncing...")
                ser.read(4)
                continue
                
            packet = (resp_id, length, payload, crc_b)
            
            if pkt_type == 'TELEM':
                telem_queue.put(packet)
            elif pkt_type == 'CMD':
                cmd_queue.put(packet)
                
        except Exception as e:
            print("Serial read error:", e)
            time.sleep(0.01)

def telem_loop():
    """Parses telemetry packets from the queue."""
    while True:
        try:
            resp_id, length, payload, crc_b = telem_queue.get()
            streamTelem.packet = payload
            streamTelem.readBuffer()
        except Exception as e:
            print("Telem error:", e)

def cmd_loop():
    """Parses command responses from the queue."""
    while True:
        try:
            resp_id, length, payload, crc_b = cmd_queue.get()
            print(f"[CMD RESPONSE] resp_id={resp_id:#04x} payload={payload.hex()}")

            if resp_id == 0x02:
                bme280.readSettings(payload)
            if resp_id == 0x03:
                lsm9ds1.readSettings(payload)
            if resp_id == 0x04:
                eeprom.readSettings(payload)
                
        except Exception as e:
            print("CMD error:", e)           

ser, activePort, activeRate = find_serial()

if activePort:
    # Start reading in background thread
    print(f"Found activity on {activePort} at {activeRate} baudrate")
    sw.init(ser) # give the writer the same serial handle
    threading.Thread(target=read_serial_loop, daemon=True).start()
    threading.Thread(target=telem_loop, daemon=True).start()
    threading.Thread(target=cmd_loop,   daemon=True).start()
else:
    print("Serial Invalid!")