import serial
import struct
import yaml

# ---------------- CONFIG ----------------
STREAMS_YAML_FILE = "C:/Git/Hybrid/tools/buses/streamDef.yaml"
BUS_YAML_FILE = "C:/Git/Hybrid/tools/buses/busDef.yaml"
SERIAL_PORT = "COM4"     
BAUD_RATE = 115200
STREAM_NAME = "streamSerialTelem"
# ---------------------------------------

# Load YAML
with open(STREAMS_YAML_FILE, "r") as f:
    streams = yaml.safe_load(f)

with open(BUS_YAML_FILE, "r") as f:
    buses = yaml.safe_load(f)
    
thisStream = streams[STREAM_NAME]

# Open the serial port
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

print("Listening for packets...")

def bytes2Volts(startByte):
    raw_volts = (packet[startByte] << 8) | packet[startByte+1]
    
    return (raw_volts / 1024) * 3.3

def bytes2Num(startByte, bytes):
    if bytes == 2:
        return (packet[startByte] << 8) | packet[startByte+1]
    if bytes == 4:
        return (packet[startByte] << 24) | (packet[startByte+1] << 16) | (packet[startByte+2] << 8) | packet[startByte+3]
    
def bytes2Float(startByte):
    # take 4 bytes and convert to float (IEEE 754)
    raw_bytes = bytes(packet[startByte:startByte+4])
    return struct.unpack('>f', raw_bytes)[0]  # >f = big-endian float

def bytes2Int16(i):
    val = (packet[i] << 8) | packet[i+1]
    #if val & 0x8000:
    #    val -= 0x10000
    return val

def find_and_read_packet():
    """Read bytes for the header and ID, then read the rest of the packet"""
    while True:
        # Read bytes until we find 0xAB
        b1 = ser.read(1)
        if len(b1) == 0:
            continue
        if b1[0] != (thisStream['header'] >> 8) & 0xFF:
            continue
        b2 = ser.read(1)
        if len(b2) == 0:
            continue
        if b2[0] != thisStream['header'] & 0xFF:
            continue
        b3 = ser.read(1)
        if len(b3) == 0:           
            continue
        if b3[0] != (thisStream['id'] >> 8) & 0xFF:
            continue
        b4 = ser.read(1)
        if len(b4) == 0:
            continue
        if b4[0] != thisStream['id'] & 0xFF:
            continue
        
        # Header found, read remaining bytes
        remaining = ser.read(thisStream['size'] - 4)
        if len(remaining) != thisStream['size'] - 4:
            print("Incomplete packet, skipping...")
            continue

        # Full packet
        packet = list(b1) + list(b2) + list(b3) + list(b4) + list(remaining)
        return packet

try:
    while True:
        packet = find_and_read_packet()

        # Decode timestamp (4 bytes)
        timestamp = (packet[4] << 24) | (packet[5] << 16) | (packet[6] << 8) | packet[7]

        sensorBIT = f"{packet[8]:08b}"
        # Print raw bytes in hex
        hex_values = [f"{b:02X}" for b in packet]
        
        idx = 9
        id1   = bytes2Num(idx, 2); idx += 2
        batt  = bytes2Volts(idx); idx += 2
        v3    = bytes2Volts(idx); idx += 2
        v5    = bytes2Volts(idx); idx += 2
        id2   = bytes2Num(idx, 2); idx += 2
        temp  = bytes2Float(idx); idx += 4
        pressure = bytes2Float(idx); idx += 4
        humidity = bytes2Float(idx); idx += 4
        alt    = bytes2Float(idx); idx += 4
        id3    = bytes2Num(idx, 2); idx += 2

        # IMU values
        accelX = bytes2Float(idx); idx += 4
        accelY = bytes2Float(idx); idx += 4
        accelZ = bytes2Float(idx); idx += 4
        magX   = bytes2Float(idx); idx += 4
        magY   = bytes2Float(idx); idx += 4
        magZ   = bytes2Float(idx); idx += 4
        gyroX  = bytes2Float(idx); idx += 4
        gyroY  = bytes2Float(idx); idx += 4
        gyroZ  = bytes2Float(idx); idx += 4
        
        
        id4    = bytes2Num(idx, 2); idx += 2
        # High-G IMU values
        highG_accelX = bytes2Float(idx); idx += 4
        highG_accelY = bytes2Float(idx); idx += 4
        highG_accelZ = bytes2Float(idx); 
        
        print(
            f"{timestamp:<10} "
            f"|| BIT: {sensorBIT} "
            f"|| ID: {id1:5d} | "
            f"Batt: {batt:5.2f}V | "
            f"3V: {v3:4.2f}V | "
            f"5V: {v5:4.1f}V | "
            f"|| ID: {id2:5d} | "
            f"Temp: {temp:4.1f}C | "
            f"Press: {(pressure/6895):4.2f}PSI | "
            f"Hum: {humidity:4.1f}% | "
            f"Alt: {alt:4.1f}m | "
            f"|| ID: {id3:5d} | "
            f"Accel: {accelX:5.1f} {accelY:5.1f} {accelZ:5.1f} | "
            f"Mag: {magX:5.1f} {magY:5.1f} {magZ:5.1f} | "
            f"Gyro: {gyroX:5.1f} {gyroY:5.1f} {gyroZ:5.1f} "
            f"|| ID: {id4:5d} | "
            f"High-G Accel XYZ: {highG_accelX:5.1f} {highG_accelY:5.1f} {highG_accelZ:5.1f} | "
        )

        #print(hex_values)


except KeyboardInterrupt:
    print("Exiting...")

finally:
    ser.close()