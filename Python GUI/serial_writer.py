"""
serial_writer.py

Sends commands to the STM32 using the same framing convention as the
existing telemetry stream:

    OUTGOING PACKET FORMAT:
    [ HEADER: 2 bytes ] [ CMD_ID: 2 bytes ] [ LEN: 1 byte ] [ PAYLOAD: LEN bytes ] [ CRC8: 1 byte ]

    HEADER  = 0xABCD  (distinct from the telem receive header 0xAB1A so the STM32 can tell them apart)
    CMD_ID  = 2-byte command identifier
    LEN     = number of payload bytes (0 if no payload)
    CRC8    = XOR of everything after the header (CMD_ID + LEN + PAYLOAD)

TO ADD A NEW COMMAND:
    1. Add a CMD_xxx constant in the "Command IDs" section
    2. Add a send_xxx() function that builds the payload and calls _send()
    Done.
"""

import struct
import threading
import time
from dataclasses import dataclass, field

# == Config =====================================================================
CMD_HEADER    = [0xDE, 0xAD]            # 1-byte start marker for outgoing commands
CMD_END       = [0xEF, 0xBE]

# == Command IDs ================================================================
CMD_PING                    = 0x01
CMD_GET_BME280_SETTINGS     = 0x02
CMD_GET_LSM9DS1_SETTINGS    = 0x03
CMD_GND_TELEM               = 0x10   # GroundStationRadioTelem. 0x04/0x05 are the EEPROM commands in Sensor Info/

# == Internal ===================================================================
_ser      = None                # set by init()
_tx_lock  = threading.Lock()   # one transmission at a time

_t0_ms = time.monotonic_ns() // 1_000_000

# Ground station -> ECU telemetry. The *_b command fields are set straight
# from the switch panel in serial_reader.sensor_loop. Sent as a command frame
# (DE AD), ID CMD_GND_TELEM, 6-byte payload, little-endian, packed:
#   uint32 timestamp_ms, uint16 commands_e
# Matches GroundStation_Payload in tools/switch_packet_test.
# Deliberately NOT the old CONTROL_Nano Switch_Payload (AB CD header, 9 bool
# bytes): DAQ_teensy acts on that one (moves servos, fires pyros).
@dataclass
class GroundStationRadioTelem:
    header:                 int   = 43962
    packet:                 bytes = field(default_factory=bytes)
    timestamp_ms:           int   = 0
    commands_e:             int   = 0

    # commands_e bit field enumeration:
    fillVlvCmd_b:           int   = 0 # b0,  1 = valve open, 0 = valve closed
    ventVlvCmd_b:           int   = 0 # b1,  1 = valve open, 0 = valve closed
    movVlvCmd_b:            int   = 0 # b2,  1 = valve open, 0 = valve closed
    spareVlvCmd_b:          int   = 0 # b3,  1 = valve open, 0 = valve closed
    radioEnableCmd_b:       int   = 0 # b4,  1 = On, 0 = off
    cameraEnableCmd_b:      int   = 0 # b5,  1 = On, 0 = off
    autoFireEnableCmd_b:    int   = 0 # b6,  1 = On, 0 = off
    recordEnableCmd_b:      int   = 0 # b7,  1 = On, 0 = off
    spare1EnableCmd_b:      int   = 0 # b8,  1 = On, 0 = off
    spare2EnableCmd_b:      int   = 0 # b9,  1 = On, 0 = off
    armCmd_b:               int   = 0 # b10, 1 = Arm, 0 = Safe
    pyroFireCmd_b:          int   = 0 # b11, 1 = Fire, 0 = off
    pyroChannel_b:          int   = 0 # b12, 1 = Channel 1, 0 = Channel 2

    def createPayload(self):
        """Build commands_e from the *_b fields, stamp timestamp_ms (ms since
        the ground station started) and pack both into self.packet."""
        self.commands_e = (
            (self.fillVlvCmd_b        & 1) << 0  |
            (self.ventVlvCmd_b        & 1) << 1  |
            (self.movVlvCmd_b         & 1) << 2  |
            (self.spareVlvCmd_b       & 1) << 3  |
            (self.radioEnableCmd_b    & 1) << 4  |
            (self.cameraEnableCmd_b   & 1) << 5  |
            (self.autoFireEnableCmd_b & 1) << 6  |
            (self.recordEnableCmd_b   & 1) << 7  |
            (self.spare1EnableCmd_b   & 1) << 8  |
            (self.spare2EnableCmd_b   & 1) << 9  |
            (self.armCmd_b            & 1) << 10 |
            (self.pyroFireCmd_b       & 1) << 11 |
            (self.pyroChannel_b       & 1) << 12
        )
        self.timestamp_ms = (time.monotonic_ns() // 1_000_000 - _t0_ms) & 0xFFFFFFFF
        self.packet = struct.pack("<IH", self.timestamp_ms, self.commands_e)
        return self.packet

gndTelem = GroundStationRadioTelem()

def _crc8(data: bytes) -> int:
    """XOR CRC over all bytes. Matches the C crc8() in serial_cmd.c."""
    crc = 0x00
    for b in data:
        crc ^= b
    return crc

def _build_packet(cmd_id: int, payload: bytes = b"") -> bytes:
    """
    Assemble a complete outgoing packet.
    Layout: [HEADER 2B][CMD_ID 2B][LEN 1B][PAYLOAD][CRC8 1B]
    CRC covers: CMD_ID + LEN + PAYLOAD
    """
    start   = bytes(CMD_HEADER)           # 2 bytes
    cmd     = struct.pack("B", cmd_id)      # 1 byte (was 2-byte, match C's uint8_t)
    length  = struct.pack("B", len(payload))
    body    = cmd + length + payload
    crc     = struct.pack("B", _crc8(body))
    end     = bytes(CMD_END)                 # FRAME_END
    return start + body + crc + end

def _send(cmd_id: int, payload: bytes = b"") -> bool:
    """
    Build and transmit a packet. Returns True on success, False if serial
    is unavailable or the write fails.
    Thread-safe.
    """
    if _ser is None or not _ser.is_open:
        print(f"[serial_writer] Cannot send cmd {cmd_id:#06x}: serial not open")
        return False

    packet = _build_packet(cmd_id, payload)
    try:
        with _tx_lock:
            _ser.write(packet)
            _ser.flush()
        return True
    except Exception as e:
        print(f"[serial_writer] Write error: {e}")
        return False

# == Public: init ===============================================================
def init(serial_handle):
    """
    Call this after serial_reader finds a port:
        import serial_writer as sw
        sw.init(sr.ser)
    """
    global _ser
    _ser = serial_handle

# == Command functions ==========================================================
# Each function is one command. Add parameters to the payload struct as needed.
# Use struct.pack() to serialise — big-endian (">") to match your existing style.

def send_gnd_telem() -> bool:
    """Send gndTelem. Returns False (quietly -- it's sent several times a
    second) if the radio port isn't open."""
    if _ser is None or not _ser.is_open:
        return False
    return _send(CMD_GND_TELEM, gndTelem.createPayload())

def send_ping() -> bool:
    print("Send ping")
    """No payload. Expect a RESP_PONG back."""
    return _send(CMD_PING)