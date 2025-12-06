import serial
import time
import struct
# -------------------------
# Configure your serial port
# -------------------------
SERIAL_PORT = "COM4"      # Replace with your port
BAUD_RATE = 115200
PACKET_SIZE = 30           # 2 bytes header + 4 bytes timestamp + 2 bytes batt

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
    """Read bytes until we find the header 0xABBA, then read the rest of the packet"""
    while True:
        # Read bytes until we find 0xAB
        b1 = ser.read(1)
        if len(b1) == 0:
            continue
        if b1[0] != 0xAB:
            continue

        # Next byte must be 0xBA
        b2 = ser.read(1)
        if len(b2) == 0:
            continue
        if b2[0] != 0xBA:
            continue
        
        b3 = ser.read(1)
        if len(b3) == 0:
            continue
        if b3[0] != 0x1A:
            continue

        # Next byte must be 0xBA
        b4 = ser.read(1)
        if len(b4) == 0:
            continue
        if b4[0] != 0xFF:
            continue

        # Header found, read remaining bytes
        remaining = ser.read(PACKET_SIZE - 4)
        if len(remaining) != PACKET_SIZE - 4:
            print("Incomplete packet, skipping...")
            continue

        # Full packet
        packet = [0xAB, 0xBA, 0x1A, 0xFF] + list(remaining)
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