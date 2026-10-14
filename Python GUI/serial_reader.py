import serial
import yaml
import threading
from collections import deque
import time
from pathlib import Path
import struct
import serial_writer as sw
import Station_Sensors as snsrs
import gui_settings as settings
import queue
from dataclasses import dataclass, field
import os
from datetime import datetime
import csv

import sys
from pathlib import Path
sensor_path = Path(__file__).parent / "Sensor Info"
sys.path.append(str(sensor_path))
import INFO_BME280 as bme280
import INFO_LSM9DS1 as lsm9ds1
import INFO_EEPROM as eeprom

# ---------------- CONFIG ----------------
SERIAL_PORT = "COM5"#["COM2","COM3","COM4","COM5","COM6","COM7","COM8"]
BAUD_RATE = 115200

STREAM_NAME = "streamSerialTelem"
MAX_POINTS = 500

TELEM_HEADER = (0xAB, 0xCD)
CMD_HEADER   = (0xDE, 0xAD)
FRAME_END    = (0xEF, 0xBE)
# ---------------------------------------

ser = None
telem_queue = queue.Queue()
cmd_queue = queue.Queue()

_log_file = None
log_writer = None
logging_enabled = False

# ---------------- HELPERS ----------------
def bytes2Num(packet, startByte, bytes):
    if bytes == 2:
        return (packet[startByte] << 8) | packet[startByte+1]
    if bytes == 4:
        return (packet[startByte] << 24) | (packet[startByte+1] << 16) | (packet[startByte+2] << 8) | packet[startByte+3]
    
def bytes2Volts(packet, startByte):
    raw_volts = (packet[startByte] << 8) | packet[startByte+1]
    return (raw_volts / 1024) * 3.3

def bytes2Float(packet, startByte):
    raw_bytes = bytes(packet[startByte:startByte+4])
    return struct.unpack('>f', raw_bytes)[0]
  
def read_sync(ser):
    """Read until we find a known 2-byte header, return which one it was."""
    b0 = ser.read(1)
    if not b0:
        return None
    b0 = b0[0]
    while True:
        b1 = ser.read(1)
        if not b1:
            return None
        b1 = b1[0]
        pair = (b0, b1)
        if pair == TELEM_HEADER:
            return 'TELEM'
        if pair == CMD_HEADER:
            return 'CMD'
        b0 = b1  # slide the window
    
def crc8(data: bytes) -> int:
    crc = 0x00
    for byte in data:
        crc ^= byte
    return crc

def check_crc(packet: bytes) -> bool:
    # packet layout: 2 start + 1 resp_id + 1 length + payload + 1 crc + 2 end
    if len(packet) < 7:
        return False
    
    payload_len = packet[3]
    crc_index = 4 + payload_len
    
    if crc_index >= len(packet):
        return False
    
    # crc is calculated over resp_id + length + payload (same as Arduino: &buf[2], 2 + payload_len)
    data_to_check = packet[2:2 + 2 + payload_len]
    calculated = crc8(data_to_check)
    received = packet[crc_index]
    
    return calculated == received
       
def init_log_raw():
    global _log_file, log_writer, logging_enabled
    
    if logging_enabled:
        close_log()
        return
    
    os.makedirs("data_logs", exist_ok=True)
    filename = f"data_logs/telem_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    _log_file = open(filename, "w", newline="")
    log_writer = csv.writer(_log_file)
    # write header
    log_writer.writerow([
        "ctrl_timestamp", "daq_timestamp", "tsy_timestamp",
        "pt1", "pt2", "pt3", "pt4", "battVolts",
        "fill", "vent", "mov", "arm", "py1", "py2", "c1", "c2",
        "ctrl_RSSI", "daq_RSSI", "tsy_looptime", "sd_state"
    ])
    
    print(f"Recording data to {filename}")
    logging_enabled = True

def log_telem(t):
    if log_writer is None:
        return
    log_writer.writerow([
        t.ctrl_timestamp, t.daq_timestamp, t.tsy_timestamp,
        t.pt1, t.pt2, t.pt3, t.pt4, t.battVolts,
        t.fill_state, t.vent_state, t.mov_state, t.arm_state,
        t.py1_state, t.py2_state, t.c1_state, t.c2_state,
        t.ctrl_RSSI, t.RSSI, t.tsy_looptime, t.sd_state
    ])
        
def close_log():
    global _log_file, logging_enabled
    if _log_file:
        _log_file.close()
        _log_file = None
        
    logging_enabled = False
    print("Stopped recording data.")
    
@dataclass      
class StreamTelem:
    header:            int   = 43962
    packet:            bytes = field(default_factory=bytes)
    ctrl_timestamp:    int   = 0
    ctrl_RSSI:         int   = 0
    ctrl_looptime:     int   = 0
    ctrl_sendtime:     int   = 0
    ctrl_waittime:     int   = 0
    daq_timestamp:     int   = 0
    daq_looptime:      int   = 0
    tsy_timestamp:     int   = 0
    tsy_looptime:      int   = 0
    valve_states:      int   = 0
    pyro_states:       int   = 0
    arm_states:        int   = 0
    sensor_states:     int   = 0
    pt1:               float = 0.0
    pt2:               float = 0.0
    pt3:               float = 0.0
    pt4:               float = 0.0
    battVolts:         float = 0.0
    battCurrent:       float = 0.0
    tc1:               float = 0.0
    tc2:               float = 0.0
    RSSI:              int = 0
    
    fill_state:        int   = 0
    vent_state:        int   = 0
    mov_state:         int   = 0
    py1_state:         int   = 0
    py2_state:         int   = 0
    arm_state:         int   = 0
    c1_state:          int   = 0
    c2_state:          int   = 0
    
    sd_state:          int   = 0
    ina219_state:      int   = 0
    ads1115_state:     int   = 0
    

    cpuTemp_c:              float = 0.0 # Station PI CPU temperature [C]
    
    # BME280
    stationTemp_c:          float = 0.0 # Station PI Hat temperature [C]
    stationBaroAlt_m:       float = 0.0 # Station PI Altitude in [m]
    
    stationADCBattVolts:    float = 0.0 # Station ADC battery voltage [V]
    stationInaBattCurrent:  float = 0.0 # Station PI Altitude in [m]
    stationInaBattSOC:      float = 0.0 # Station battery state of charge [%]
    stationADCChargeVolts:  float = 0.0 # Station USB charging voltage [V]
    stationCharging_b:      int   = 0   # 1 = battery is charging
    stationADCRadioVolts:   float = 0.0 # Station ADC radio voltage [V]
    stationInaBattPower:    float = 0.0 # Station INA battery power [W]
    stationInaBattVolts:    float = 0.0 # Station INA battery voltage [V]

    # GPS (MAX-M10S, via NMEA GGA/RMC)
    gpsFixValid_b:      int   = 0     # True once a GGA/RMC sentence reports a valid fix
    gpsLat:             float = 0.0   # signed decimal degrees, +N/-S
    gpsLon:             float = 0.0   # signed decimal degrees, +E/-W
    gpsAlt_m:           float = 0.0   # altitude above mean sea level, from GGA
    gpsNumSV:           int   = 0     # satellites in use, from GGA
    gpsHDOP:            float = 0.0   # horizontal dilution of precision, from GGA
    gpsSpeed_kts:       float = 0.0   # ground speed in knots, from RMC
    gpsCourse_deg:      float = 0.0   # course over ground in degrees true, from RMC
    gpsTime:            object = None # UTC time (datetime.time), from GGA/RMC
    gpsDate:            object = None # UTC date (datetime.date), from RMC
    gpsSatsVisible:     int   = 0     # satellites in view (tracked, not necessarily used), from GSV
    gpsMaxCNO:          float = 0.0   # best C/N0 signal strength seen, dB-Hz, from GSV




    def readBuffer(self):
        import struct
        (self.ctrl_timestamp, 
        self.ctrl_RSSI, 
        self.ctrl_looptime, 
        self.ctrl_sendtime,
        self.ctrl_waittime,
        self.tsy_timestamp,
        self.valve_states,
        self.pyro_states,
        self.arm_states,
        self.sensor_states,
        self.pt1,
        self.pt2,
        self.pt3,
        self.pt4,
        self.battVolts,
        self.battCurrent,
        self.tc1,
        self.tc2,
        self.RSSI,
        self.tsy_looptime) = struct.unpack_from("<"
                                        "IbIII"               # ctrl: timestamp (uint32), RSSI (int8), looptime (uint32)
                                        "IBBBBffffffffbI",  # tsy: timestamp, valve/pyro/arm states, pt1-4, batt voltage, batt current, tc1, tc2, RSSI, looptime
                                        bytes(self.packet))
        
        self.fill_state     = (self.valve_states >> 0) & 1
        self.vent_state     = (self.valve_states >> 1) & 1
        self.mov_state      = (self.valve_states >> 2) & 1

        self.py1_state      = (self.pyro_states >> 0) & 1
        self.py2_state      = (self.pyro_states >> 1) & 1

        self.arm_state      = (self.arm_states >> 0) & 1
        self.c1_state       = (self.arm_states >> 1) & 1 
        self.c2_state       = (self.arm_states >> 2) & 1 
        
        self.sd_state       = (self.sensor_states >> 0) & 1
        self.ina219_state   = (self.sensor_states >> 1) & 1
        self.ads1115_state  = (self.sensor_states >> 2) & 1


    
streamTelem = StreamTelem()     


def find_serial():
    try:
        ser = serial.Serial(
            SERIAL_PORT,
            BAUD_RATE,
            timeout=1,
            xonxoff=False,    # disable software flow control
            rtscts=False,     # disable hardware flow control
            dsrdtr=False      # disable DSR/DTR flow control
        )
        return ser, SERIAL_PORT, BAUD_RATE
    except serial.SerialException:
        pass
    return None, None, None

def read_serial_loop():
    global ser
    while True:
        try:
            pkt_type = read_sync(ser)
            if pkt_type is None:
                continue

            header = ser.read(2)
            if len(header) < 2:
                print(f"[TELEM] Header too short: {header.hex()}")
                continue
            resp_id = header[0]
            length  = header[1]
            payload = ser.read(length) if length > 0 else b""
            crc_b   = ser.read(1)
            end_b   = ser.read(2)
            
            # check crc
            calculated = crc8(bytes([resp_id, length]) + payload)
            if len(crc_b) < 1 or calculated != crc_b[0]:
                print(f"[TELEM] CRC mismatch: got {crc_b.hex() if crc_b else 'none'}, expected {calculated:02X}")
                continue
            
            if len(payload) != length:
                print(f"[TELEM] Dropped packet. Incorrect length {len(payload)}, {length}")
                continue

            if not end_b or len(end_b) < 2:
                print("[ROUTER] No frame end, re-syncing...")
                continue

            if end_b[0] != FRAME_END[0] or end_b[1] != FRAME_END[1]:
                print(f"[ROUTER] Bad frame end: {end_b.hex()}, re-syncing...")
                continue
            
            packet = (resp_id, length, payload, crc_b)

            if pkt_type == 'TELEM':
                telem_queue.put(packet)
            elif pkt_type == 'CMD':
                cmd_queue.put(packet)
               
        except (serial.SerialException, PermissionError, OSError) as e:
            print(f"Serial disconnected: {e}")
            # close the dead handle
            try:
                ser.close()
            except:
                pass
            ser = None
            # wait and try to reconnect
            while ser is None:
                time.sleep(2)
                print("Attempting reconnect...")
                new_ser, port, rate = find_serial()
                if new_ser:
                    ser = new_ser
                    sw.init(ser)
                    print(f"Reconnected on {port}") 
                                   
        except Exception as e:
            print("Serial read error:", e)
            time.sleep(0.01)

def telem_loop():
    """Parses telemetry packets from the queue."""
    while True:
        try:
            resp_id, length, payload, crc_b = telem_queue.get()
            streamTelem.packet = payload
            streamTelem.readBuffer()
            if logging_enabled:
                log_telem(streamTelem) 
                
        except Exception as e:
            import traceback; traceback.print_exc()

def cmd_loop():
    """Parses command responses from the queue."""
    while True:
        try:
            resp_id, length, payload, crc_b = cmd_queue.get()
            print(f"[CMD RESPONSE] resp_id={resp_id:#04x} payload={payload.hex()}")

            if resp_id == 0x02:
                bme280.readSettings(payload)
            if resp_id == 0x03:
                lsm9ds1.readSettings(payload)
            if resp_id == 0x04:
                eeprom.readSettings(payload)
                
        except Exception as e:
            print("CMD error:", e)           

def sensor_loop():
    while True:
        try:
            # bme280/ads1115 share one Blinka i2c object across threads -- lock
            # it for the duration of these reads so transactions can't interleave.
            with snsrs.i2c_lock:
                streamTelem.stationTemp_c = snsrs.bme280.temperature
                streamTelem.stationBaroAlt_m = snsrs.bme280.altitude

                streamTelem.stationChargeVolts = snsrs.vusb_mon_v.voltage * 1.67727393264
                streamTelem.stationADCBattVolts = snsrs.batt_mon_v.voltage * 2.97230769231
                streamTelem.stationADCRadioVolts = snsrs.radio_mon_v.voltage * 2.97230769231

            # ina219 is on its own separate smbus handle, not the shared i2c bus.
            streamTelem.stationInaBattCurrent = snsrs.ina.current() / 1000
            streamTelem.stationInaBattPower = snsrs.ina.power() / 1000
            streamTelem.stationInaBattVolts = snsrs.ina.voltage()

        except Exception as e:
            print("Sensor error:", e)


def gps_loop():
    """Continuously reads and parses NMEA/UBX messages from the MAX-M10S
    over I2C, updating the GPS fields on streamTelem as sentences arrive."""
    # MAX-M10S interleaves GSV sentences from multiple constellations
    # (GPGSV, GLGSV, GAGSV, GBGSV...), each with its own independent
    # msgNum/numMsg sequence, so each talker ID needs its own accumulator
    # -- otherwise one constellation's scan starting resets another's
    # still-in-progress one.
    gps_loop.cno_accum = {}    # identity -> cnos accumulated so far this scan
    gps_loop.cno_best = {}     # identity -> best cno from its last completed scan
    while True:
        try:
            _, parsed = snsrs.gps_reader.read()
            if parsed is None:
                continue

            identity = getattr(parsed, "identity", "")

            # pynmeagps returns "" (not a number/time/date) for any field a
            # sentence leaves blank, e.g. lat/lon/alt before the GPS has a
            # fix. Only overwrite a telemetry field when the parsed value is
            # actually usable, so we don't clobber the last good reading.
            def setfield(name, value):
                if value != "":
                    setattr(streamTelem, name, value)

            if identity.endswith("GGA"):
                setfield("gpsLat", parsed.lat)
                setfield("gpsLon", parsed.lon)
                setfield("gpsAlt_m", parsed.alt)
                setfield("gpsNumSV", parsed.numSV)
                setfield("gpsHDOP", parsed.HDOP)
                setfield("gpsTime", parsed.time)
                streamTelem.gpsFixValid_b = int(parsed.quality > 0)

            elif identity.endswith("RMC"):
                setfield("gpsLat", parsed.lat)
                setfield("gpsLon", parsed.lon)
                setfield("gpsSpeed_kts", parsed.spd)
                setfield("gpsCourse_deg", parsed.cog)
                setfield("gpsTime", parsed.time)
                setfield("gpsDate", parsed.date)
                streamTelem.gpsFixValid_b = int(parsed.status == "A")

            elif identity.endswith("GSV"):
                # GSV reports satellites *in view* with signal strength (C/N0),
                # independent of whether a fix has been computed yet -- useful
                # to tell "no signal reaching the receiver" apart from
                # "acquiring, just needs more time".
                setfield("gpsSatsVisible", parsed.numSV)

                if getattr(parsed, "msgNum", 1) == 1:
                    gps_loop.cno_accum[identity] = []

                accum = gps_loop.cno_accum.setdefault(identity, [])
                for key in ("cno", "cno_01", "cno_02", "cno_03"):
                    val = getattr(parsed, key, "")
                    if isinstance(val, (int, float)):
                        accum.append(val)

                if getattr(parsed, "msgNum", 1) == getattr(parsed, "numMsg", 1):
                    gps_loop.cno_best[identity] = max(accum) if accum else 0.0
                    streamTelem.gpsMaxCNO = max(gps_loop.cno_best.values())

        except Exception as e:
            print("GPS error:", e)


def buzzer_loop():
    """Pulses the ground-station buzzer on for settings.BUZZER_ON_DURATION_S
    every settings.BUZZER_INTERVAL_S seconds."""
    while True:
        try:
            if not settings.BUZZER_ENABLED:
                snsrs.buzzer.off()
                time.sleep(settings.BUZZER_INTERVAL_S)
                continue

            snsrs.buzzer.value = 0.5  # 50% duty square wave at BUZZER_FREQUENCY_HZ -> audible tone
            time.sleep(settings.BUZZER_ON_DURATION_S)
            snsrs.buzzer.off()
            time.sleep(max(settings.BUZZER_INTERVAL_S - settings.BUZZER_ON_DURATION_S, 0))
        except Exception as e:
            print("Buzzer error:", e)


ser, activePort, activeRate = find_serial()
threading.Thread(target=sensor_loop,   daemon=True).start()
threading.Thread(target=buzzer_loop,   daemon=True).start()
threading.Thread(target=gps_loop,      daemon=True).start()
if activePort:
    # Start reading in background thread
    print(f"Found activity on {activePort} at {activeRate} baudrate")
    sw.init(ser) # give the writer the same serial handle
    #init_log_raw()
    threading.Thread(target=read_serial_loop, daemon=True).start()
    threading.Thread(target=telem_loop, daemon=True).start()
    threading.Thread(target=cmd_loop,   daemon=True).start()
    
else:
    print("Serial Invalid!")