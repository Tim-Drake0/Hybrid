import subprocess
import time

def open_putty_serial(com_port, baud_rate):
    """
    Opens a PuTTY serial session with the specified COM port and baud rate.

    Args:
        com_port (str): The COM port to connect to (e.g., "COM1", "/dev/ttyUSB0").
        baud_rate (int): The baud rate for the serial connection.
    """
    try:
        # Construct the PuTTY command with serial parameters
        putty_command = [
            "putty",
            "-serial", com_port,
            "-sercfg", f"{baud_rate},8,n,1,N"  # Example: baud, data bits, parity, stop bits, flow control
        ]

        print(f"Opening PuTTY serial session to {com_port} at {baud_rate} baud...")
        # Use subprocess.Popen to open PuTTY in a new window
        subprocess.Popen(putty_command)
        print("PuTTY session launched.")

    except FileNotFoundError:
        print("Error: PuTTY executable not found. Please ensure PuTTY is installed and in your system's PATH.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    serial_port = "/dev/ttyV0" 
    baudrate = 9600

    open_putty_serial(serial_port, baudrate)



    time.sleep(5)
    print("PuTTY window opened. You can now manually interact with it.")