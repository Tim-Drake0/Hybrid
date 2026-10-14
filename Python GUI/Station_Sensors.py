import time
import threading
import board
from adafruit_bme280 import basic as adafruit_bme280
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from ina219 import INA219
from ina219 import DeviceRangeError
from gpiozero import PWMOutputDevice
from pyubx2 import UBXReader, NMEA_PROTOCOL, UBX_PROTOCOL
from smbus2 import SMBus, i2c_msg
import gui_settings as settings

i2c = board.I2C()  # uses board.SCL and board.SDA

# bme280/ads1115 share this `i2c` (Blinka) object and may be accessed from
# different threads, so every transaction through it must be serialized with
# this lock. ina219 and the GPS are each on their own separate smbus handles
# (see below) so they don't need it.
i2c_lock = threading.Lock()

# Passive buzzer: needs a driven square wave (not just DC) to produce a tone.
buzzer = PWMOutputDevice(settings.BUZZER_GPIO_PIN, frequency=settings.BUZZER_FREQUENCY_HZ)


bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)

ads = ADS.ADS1115(i2c, address=0x49)
# 2/3 = +/-6.144V, 1 = +/-4.096V, 2 = +/-2.048V
ads.gain = 1 

# 4. Assign the pin channel (0 corresponds to hardware pin A0)
vusb_mon_v = AnalogIn(ads, 0)
batt_mon_v = AnalogIn(ads, 1)
spare_mon_v = AnalogIn(ads, 2)
radio_mon_v = AnalogIn(ads, 3)

# Define your shunt resistor ohm value and maximum expected current
SHUNT_OHMS = 0.05
MAX_EXPECTED_AMPS = 4

ina = INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS, busnum=1, address=0x45)
ina.configure(ina.RANGE_16V)


# ---------------- MAX-M10S GPS (I2C / DDC) ----------------
GPS_I2C_ADDRESS = 0x42


class I2CGPSStream:
    """File-like read()/readline()/write() wrapper around a u-blox module's
    I2C (DDC) interface, so pyubx2's UBXReader can read it like a serial port.

    Uses smbus2 directly (raw I2C_RDWR ioctl via i2c_msg) rather than Blinka,
    on its own SMBus handle -- a separate, independently-verifiable transport
    from the bme280/ads1115 (Blinka) and ina219 (Adafruit_GPIO/smbus) paths.
    The kernel serializes actual bus transactions per adapter regardless of
    which file descriptor issues them, so this doesn't need i2c_lock.

    Per the u-blox integration manual: register 0xFD/0xFE (big-endian) holds
    the number of bytes currently buffered and ready to read, and the data
    itself is streamed by repeatedly reading register 0xFF. Writes go
    straight to the device with no register prefix.
    """

    BYTES_AVAILABLE_REG = 0xFD
    DATA_STREAM_REG = 0xFF

    def __init__(self, bus_num, address, timeout=2.0, poll_interval=0.01):
        self._bus = SMBus(bus_num)
        self._address = address
        self._timeout = timeout
        self._poll_interval = poll_interval

    def _bytes_available(self):
        write = i2c_msg.write(self._address, [self.BYTES_AVAILABLE_REG])
        read = i2c_msg.read(self._address, 2)
        self._bus.i2c_rdwr(write, read)
        hi, lo = bytes(read)
        return (hi << 8) | lo

    def _read_available(self, n):
        write = i2c_msg.write(self._address, [self.DATA_STREAM_REG])
        read = i2c_msg.read(self._address, n)
        self._bus.i2c_rdwr(write, read)
        return bytes(read)

    def read(self, n=1):
        """Block until exactly n bytes are read, or raise TimeoutError."""
        deadline = time.monotonic() + self._timeout
        data = bytearray()
        while len(data) < n:
            avail = self._bytes_available()
            if avail == 0:
                if time.monotonic() > deadline:
                    raise TimeoutError("MAX-M10S: no data available over I2C")
                time.sleep(self._poll_interval)
                continue
            data += self._read_available(min(avail, n - len(data)))
        return bytes(data)

    def readline(self):
        """Block until a full LF-terminated line is read (NMEA framing)."""
        deadline = time.monotonic() + self._timeout
        line = bytearray()
        while True:
            line += self.read(1)
            if line[-1:] == b"\n":
                return bytes(line)
            if time.monotonic() > deadline:
                raise TimeoutError("MAX-M10S: incomplete NMEA line over I2C")

    def write(self, data: bytes):
        self._bus.i2c_rdwr(i2c_msg.write(self._address, bytes(data)))


gps_stream = I2CGPSStream(1, GPS_I2C_ADDRESS)
gps_reader = UBXReader(gps_stream, protfilter=NMEA_PROTOCOL | UBX_PROTOCOL)