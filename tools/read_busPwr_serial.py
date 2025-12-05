import serial
import time

# -------------------------
# Configure your serial port
# -------------------------
SERIAL_PORT = "COM4"      # Replace with your port
BAUD_RATE = 115200
PACKET_SIZE = 20           # 2 bytes header + 4 bytes timestamp + 2 bytes batt

# Open the serial port
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

print("Listening for packets...")

def bytes2Volts(startByte):
    raw_volts = (packet[startByte] << 8) | packet[startByte+1]
    
    return round(((raw_volts / 1024) * 3.3),3)
  
def bytes2Temp(startByte):
    raw_temp = (packet[startByte] << 8) | packet[startByte+1]
    
    return round(raw_temp,3)  

def bytes2Num(startByte, bytes):
    if bytes == 2:
        return (packet[startByte] << 8) | packet[startByte+1]
    if bytes == 4:
        return (packet[startByte] << 24) | (packet[startByte+1] << 16) | (packet[startByte+2] << 8) | packet[startByte+3]
    
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
        
        #battVolts = (bytes2Volts(6) *9870) / 3250 #9.87k, 3.25k
        
        # Print interpreted values
        # print(
        #     f"{timestamp:<10} "  # timestamp left-aligned, 20 chars wide
        #     f"Batt: {battVolts:5.2f} "  # 6 chars wide, 2 decimals
        #     f"3V: {bytes2Volts(8):5.2f} "
        #     f"5V: {bytes2Volts(10):5.2f} "
        #     f"Sensor BIT: {format(packet[12], '08b')} "
        #     f"TEMP: {bytes2Temp(13):6.2f} "
        # )
        
        # BME280:
        print(
            f"{timestamp:<10} "  # timestamp left-aligned, 20 chars wide
            f"Temp: {bytes2Num(8,4):6.2f} "  # 6 chars wide, 2 decimals
            f"Pressure: {bytes2Num(12,4):6.2f} "
            f"Humidity: {bytes2Num(16,4):6.2f} "
        )
        
        #print(hex_values)


except KeyboardInterrupt:
    print("Exiting...")

finally:
    ser.close()