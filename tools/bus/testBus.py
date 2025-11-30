import serial
import time

# Configure the serial port parameters
# Replace '/dev/ttyUSB0' with your actual port name
SERIAL_PORT = '/dev/ttyV1' 
BAUD_RATE = 9600 # Ensure this matches the device's baud rate

try:
    # Open the serial connection
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2) # Give the port a moment to initialize/for the device to reset

    print(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud rate")

    # --- Writing to the serial port ---
    message_to_send = "Hello, device! \r\n"
    # Serial ports expect bytes, so encode the string
    ser.write(message_to_send.encode('ascii')) 
    print(f"Sent: {message_to_send}")

    # --- Reading from the serial port ---
    # Read a line terminated with a newline character
    response_bytes = ser.readline() 
    
    if response_bytes:
        # Decode the bytes into a string and remove leading/trailing whitespace
        response_string = response_bytes.decode('ascii').strip()
        print(f"Received: {response_string}")
    else:
        print("No response received within the timeout period.")

except serial.SerialException as e:
    print(f"Error accessing serial port: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    if ser and ser.isOpen():
        ser.close()
        print("Serial port closed.")

