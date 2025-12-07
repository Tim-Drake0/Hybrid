import serial
import time
import struct
import yaml

# ---------------- CONFIG ----------------
STREAMS_YAML_FILE = "C:/Git/Hybrid/tools/buses/streamDef.yaml"
SERIAL_PORT = "COM4"     
BAUD_RATE = 115200
STREAM_NAME = "streamSerialTelem"
# ---------------------------------------

# Load YAML
with open(STREAMS_YAML_FILE, "r") as f:
    streams = yaml.safe_load(f)
    
thisStream = streams[STREAM_NAME]

# Open the serial port
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

print("Listening for packets...")

def bytes2Volts(startByte):
    raw_volts = (packet[startByte] << 8) | packet[startByte+1]
    
    return (raw_volts / 1024) * 3.3
  
def bytes2Temp(startByte):
    raw_temp = (packet[startByte] << 8) | packet[startByte+1]
    
    return raw_temp

def bytes2Num(startByte, bytes):
    if bytes == 2:
        return (packet[startByte] << 8) | packet[startByte+1]
    if bytes == 4:
        return (packet[startByte] << 24) | (packet[startByte+1] << 16) | (packet[startByte+2] << 8) | packet[startByte+3]
    
def bytes2Float(startByte):
    # take 4 bytes and convert to float (IEEE 754)
    raw_bytes = bytes(packet[startByte:startByte+4])
    return struct.unpack('>f', raw_bytes)[0]  # >f = big-endian float

def find_and_read_packet():
    """Read bytes for the header and ID, then read the rest of the packet"""
    while True:
        # Read bytes until we find 0xAB
        bytes = ser.read(4)
        if len(bytes) == 0:
            continue
        if bytes[0] != (thisStream['header'] >> 8) & 0xFF:
            continue
        if bytes[1] != thisStream['header'] & 0xFF:
            continue
        if bytes[2] != (thisStream['id'] >> 8) & 0xFF:
            continue
        if bytes[3] != thisStream['id'] & 0xFF:
            continue
        
        # Header found, read remaining bytes
        remaining = ser.read(thisStream['size'] - 4)
        if len(remaining) != thisStream['size'] - 4:
            print("Incomplete packet, skipping...")
            continue

        # Full packet
        packet = list(bytes) + list(remaining)
        return packet

try:
    while True:
        packet = find_and_read_packet()

        # Decode timestamp (4 bytes)
        timestamp = (packet[4] << 24) | (packet[5] << 16) | (packet[6] << 8) | packet[7]

        # Print raw bytes in hex
        hex_values = [f"{b:02X}" for b in packet]
        
        pressurePSI = bytes2Float(18) / 6895
        
        print(
            f"{timestamp:<10} "  # timestamp left-aligned, 20 chars wide
            f"Batt: {bytes2Volts(8):5.2f}V "  # 6 chars wide, 2 decimals
            f"3V: {bytes2Volts(10):4.2f}V "
            f"5V: {bytes2Volts(12):4.1f}V "
            f"Temp: {bytes2Float(14):4.1f}C "  # 6 chars wide, 2 decimals
            f"Press: {pressurePSI:4.2f}PSI "
            f"Hum: {bytes2Float(22):4.1f}% "
            f"Alt: {bytes2Float(26):4.1f}m "
        )
        
        #print(hex_values)


except KeyboardInterrupt:
    print("Exiting...")

finally:
    ser.close()