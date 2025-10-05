import serial
import time
import struct



def read_serial_data(port, baudrate, timeout=1):
    try:
        START_MARKER = 0xAA
        PACKET_SIZE = 19  # Update based on actual length

        # Open the serial port
        ser = serial.Serial(port, baudrate, timeout=timeout)
        print(f"Opened serial port: {port} at {baudrate} baud.")
        
        while True:
            start = ser.read(1)
            if not start:
                continue  # No data, try again
            #print(start)
            if start[0] == START_MARKER:
                #print('might have packet')
                data = ser.read(PACKET_SIZE)  # Already read 1 byte
                if len(data) != PACKET_SIZE:
                    continue  # Incomplete packet, discard
                try:
                    unpacked = struct.unpack('<I3f3B', data)
                    timestamp = unpacked[0]
                    battVolts = unpacked[1]
                    load_cell = unpacked[2]
                    pt_tank = unpacked[3]
                    rssi = unpacked[4]
                    c1 = unpacked[5]
                    c2 = unpacked[6]
                    
                    print(f"Time: {timestamp/1000} s")
                    print(f"C1: {bool(c1)}, C2: {bool(c2)}")
                    print(f"Load Cell: {load_cell:.2f} N")
                    print(f"Tank Pressure: {pt_tank:.2f} psi")
                    print(f"Battery Voltage: {battVolts:.2f} V")
                    print(f"RSSI: -{rssi} dBm")
                    print("-" * 40)
                    
                    
                    #print(f"Time: {timestamp/1000} s, Batt: {round(battVolts,2)}V")
                    
                except struct.error:
                    print("Struct unpack error, skipping packet")

    except serial.SerialException as e:
        print(f"Serial port error: {e}")
    except KeyboardInterrupt:
        print("Program terminated by user.")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Serial port closed.")

# Example usage:
if __name__ == "__main__":
    # Replace with your actual serial port and baud rate
    serial_port = 'COM4'  # For Windows
    # serial_port = '/dev/ttyUSB0' # For Linux
    baud_rate = 9600

    read_serial_data(serial_port, baud_rate)