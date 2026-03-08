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

# == Config =====================================================================
CMD_HEADER    = [0xDE, 0xAD]            # 1-byte start marker for outgoing commands
CMD_END       = [0xEF, 0xBE]

# == Command IDs ================================================================
CMD_PING                    = 0x01
CMD_GET_BME280_SETTINGS     = 0x02
CMD_GET_LSM9DS1_SETTINGS    = 0x03
# == Internal ===================================================================
_ser      = None                # set by init()
_tx_lock  = threading.Lock()   # one transmission at a time

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

def send_ping() -> bool:
    print("Send ping")
    """No payload. Expect a RESP_PONG back."""
    return _send(CMD_PING)