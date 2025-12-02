import serial
import time

# -------------------------
# Configure your serial port
# -------------------------
SERIAL_PORT = "COM3"      # Replace with your port
BAUD_RATE = 115200
PACKET_SIZE = 12           # 2 bytes header + 4 bytes timestamp + 2 bytes batt

# Open the serial port
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)  # wait for Arduino to reset

print("Listening for packets...")

def bytes2Volts(startByte):
    raw_volts = (packet[startByte] << 8) | packet[startByte+1]
    
    return round(((raw_volts / 1024) * 5),2)
    
    
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

        # Header found, read remaining bytes
        remaining = ser.read(PACKET_SIZE - 2)
        if len(remaining) != PACKET_SIZE - 2:
            print("Incomplete packet, skipping...")
            continue

        # Full packet
        packet = [0xAB, 0xBA] + list(remaining)
        return packet

try:
    while True:
        packet = find_and_read_packet()

        # Decode timestamp (4 bytes)
        timestamp = (packet[2] << 24) | (packet[3] << 16) | (packet[4] << 8) | packet[5]

        # Print raw bytes in hex
        hex_values = [f"{b:02X}" for b in packet]
        
        # Print interpreted values
        print(f"{timestamp} Batt: {bytes2Volts(6)} 3V: {bytes2Volts(8)} 5V: {bytes2Volts(10)} Packet (hex): {hex_values}")

except KeyboardInterrupt:
    print("Exiting...")

finally:
    ser.close()