import serial
import struct
import yaml

# ---------------- CONFIG ----------------
STREAMS_YAML_FILE = "C:/Git/Hybrid/tools/buses/streamDef.yaml"
BUS_YAML_FILE = "C:/Git/Hybrid/tools/buses/busDef.yaml"
SERIAL_PORT = "COM4"     
BAUD_RATE = 1000000
STREAM_NAME = "streamSerialTelem"
# ---------------------------------------

# Load YAML
with open(STREAMS_YAML_FILE, "r") as f:
    streams = yaml.safe_load(f)

with open(BUS_YAML_FILE, "r") as f:
    buses = yaml.safe_load(f)
    
thisStream = streams[STREAM_NAME]



bus2print = "busLSM9DS1"

if bus2print == "busPwr":
    busID = 6910
    packetSize = 14
elif bus2print == "busBME280":
    busID = 6911
    packetSize = 24
elif bus2print == "busLSM9DS1":
    busID = 6912
    packetSize = 44
elif bus2print == "busADXL375":
    busID = 6913
    packetSize = 20
    
    

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
        b1 = ser.read(1)
        if len(b1) == 0:           
            continue
        
        if b1[0] != (busID >> 8) & 0xFF:
            continue
        
        b2 = ser.read(1)
        if len(b2) == 0:
            continue
        if b2[0] != busID & 0xFF:
            continue
       
        
        # Header found, read remaining bytes
        
        remaining = ser.read(packetSize - 1)
        if len(remaining) != packetSize - 1:
            print("Incomplete packet, skipping...")
            continue

        # Full packet
        packet = list(b1) + list(b2)+ list(remaining)
        return packet

try:
    lastTimeStamp = 0
    while True:
        packet = find_and_read_packet()
        # Print raw bytes in hex
        hex_values = [f"{b:02X}" for b in packet]
        
        if bus2print == "busPwr":
            idx = 0
            id   = bytes2Num(idx, 2); idx += 2
            timestamp = (packet[idx] << 24) | (packet[idx+1] << 16) | (packet[idx+2] << 8) | packet[idx+3]; idx += 4
            packetsSent = bytes2Num(idx, 2); idx += 2
            batt  = bytes2Volts(idx); idx += 2
            v3    = bytes2Volts(idx); idx += 2
            v5    = bytes2Volts(idx); idx += 2
        
            print(
                f"{timestamp:<8} "
                f"|| ID: {id:5d} | "
                f"Packets Sent: {packetsSent:7d} | "
                f"Batt: {batt:5.2f}V | "
                f"3V: {v3:4.2f}V | "
                f"5V: {v5:4.1f}V | "
            )
            
        elif bus2print == "busBME280":
            idx = 0
            id   = bytes2Num(idx, 2); idx += 2
            timestamp = (packet[idx] << 24) | (packet[idx+1] << 16) | (packet[idx+2] << 8) | packet[idx+3]; idx += 4
            packetsSent = bytes2Num(idx, 2); idx += 2            
            temp  = bytes2Float(idx); idx += 4
            pressure = bytes2Float(idx); idx += 4
            humidity = bytes2Float(idx); idx += 4
            alt    = bytes2Float(idx); idx += 4

            print(
                f"{timestamp:<8} "
                f"|| ID: {id:5d} | "
                f"Packets Sent: {packetsSent:7d} | "
                f"Temp: {temp:4.1f}C | "
                f"Press: {(pressure/6895):4.2f}PSI | "
                f"Hum: {humidity:4.1f}% | "
                f"Alt: {alt:4.1f}m | "
            )
        elif bus2print == "busLSM9DS1":
            idx = 0
            id   = bytes2Num(idx, 2); idx += 2
            timestamp = (packet[idx] << 24) | (packet[idx+1] << 16) | (packet[idx+2] << 8) | packet[idx+3]; idx += 4
            packetsSent = bytes2Num(idx, 2); idx += 2  
            
            accelX = bytes2Float(idx); idx += 4
            accelY = bytes2Float(idx); idx += 4
            accelZ = bytes2Float(idx); idx += 4
            magX   = bytes2Float(idx); idx += 4
            magY   = bytes2Float(idx); idx += 4
            magZ   = bytes2Float(idx); idx += 4
            gyroX  = bytes2Float(idx); idx += 4
            gyroY  = bytes2Float(idx); idx += 4
            gyroZ  = bytes2Float(idx); idx += 4
            
            print(
                f"{timestamp:<8} "
                f"|| ID: {id:5d} | "
                f"Packets Sent: {packetsSent:7d} | "
                f"Accel: {accelX:5.1f} {accelY:5.1f} {accelZ:5.1f} | "
                f"Mag: {magX:5.1f} {magY:5.1f} {magZ:5.1f} | "
                f"Gyro: {gyroX:5.1f} {gyroY:5.1f} {gyroZ:5.1f} "
                f"Frequency Sent: {1/((timestamp - lastTimeStamp)/1000):7.0f} | "
            )
            
            lastTimeStamp = timestamp
            
            
        elif bus2print == "busADXL375":
            idx = 0
            id   = bytes2Num(idx, 2); idx += 2
            timestamp = (packet[idx] << 24) | (packet[idx+1] << 16) | (packet[idx+2] << 8) | packet[idx+3]; idx += 4
            packetsSent = bytes2Num(idx, 2); idx += 2  
            
            highG_accelX = bytes2Float(idx); idx += 4
            highG_accelY = bytes2Float(idx); idx += 4
            highG_accelZ = bytes2Float(idx); idx += 4
            
            print(
                f"{timestamp:<8} "
                f"|| ID: {id:5d} | "
                f"Packets Sent: {packetsSent:7d} | "
                f"High-G Accel XYZ: {highG_accelX:5.1f} {highG_accelY:5.1f} {highG_accelZ:5.1f} | "
                f"Frequency Sent: {1/((timestamp - lastTimeStamp)/1000):7.0f} | "
            )
            
            lastTimeStamp = timestamp



        #print(hex_values)


except KeyboardInterrupt:
    print("Exiting...")

finally:
    ser.close()