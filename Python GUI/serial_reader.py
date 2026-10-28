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
SERIAL_PORT = settings.RADIO_SERIAL_PORT_PI if snsrs.ON_PI else settings.RADIO_SERIAL_PORT_PC
BAUD_RATE = settings.RADIO_BAUD_RATE

STREAM_NAME = "streamSerialTelem"
MAX_POINTS = 500

TELEM_HEADER = (0xAB, 0xCD)
CMD_HEADER   = (0xDE, 0xAD)
FRAME_END    = (0xEF, 0xBE)
ECU_TELEM_ID = 0x20   # ECURadioTelem (0x69 is the legacy DAQ telemetry -> streamTelem)
ECU_LINK_TIMEOUT_S = 3  # no ECU packet for this long = link lost (feedback LEDs go off, GUI shows DISCONNECTED)
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
    
def lipo_2s_percent(voltage: float) -> int:
    # 2S voltage -> approximate % remaining
    curve = [
        (8.40, 100),
        (8.16, 90),
        (8.00, 80),
        (7.84, 70),
        (7.60, 60),
        (7.44, 50),
        (7.36, 40),
        (7.20, 30),
        (7.04, 20),
        (6.90, 20),
        (6.80, 0),
    ]
    
    if voltage >= curve[0][0]:  return 100
    if voltage <= curve[-1][0]: return 0
    
    for i in range(len(curve) - 1):
        v_high, p_high = curve[i]
        v_low,  p_low  = curve[i + 1]
        if v_low <= voltage <= v_high:
            # linear interpolation between points
            t = (voltage - v_low) / (v_high - v_low)
            return round(p_low + t * (p_high - p_low))
    
    return 0 
    
@dataclass      
class StreamTelem:
    header:            int   = 43962
    packet:            bytes = field(default_factory=bytes)
    ctrl_timestamp:    int   = 0
    stationRSSI:       int   = -120
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
    
    # Rocket Parameters
    rktECUTemp:             float = 0.0 # temp of the Engine control unit
    rktECUVolts:            float = 0.0
    rktECUCurrent:          float = 0.0
    rktAlt:                 int   = 0
    rktVerticalVelocity:    int   = 0
    rktMaxVel:              int   = 0
    rktMaxMach:             int   = 0
    rktMaxAlt:              int   = 0
    rktMaxG:                int   = 0
    

    # Ground Station Parameters
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

    # BQ25887 2S charger (see Station_Sensors.BQ25887.poll)
    chgrConnected_b:        int   = 0     # 1 = last poll of the charger succeeded
    chgrReapplyCount:       int   = 0     # times settings were re-written after the chip reset them
    chgrPartNum:            int   = 0     # 5 = BQ25887
    chgrDevRev:             int   = 0
    chgrChargeStat:         int   = 0     # 0 none, 1 trickle, 2 pre, 3 fast CC, 4 taper CV, 5 top-off, 6 done
    chgrChargeStatStr:      str   = ""
    chgrCharging_b:         int   = 0     # 1 = in any active charge phase
    chgrPowerGood_b:        int   = 0
    chgrVbusStat:           int   = 0     # input source type, see chgrVbusStatStr
    chgrVbusStatStr:        str   = ""
    chgrIcoStat:            int   = 0     # 0 disabled, 1 optimizing, 2 max current found
    chgrIcoStatStr:         str   = ""
    chgrIcoIlim_ma:         int   = 0     # input current limit chosen by ICO [mA]
    chgrIindpm_b:           int   = 0     # 1 = input current limit is throttling charge
    chgrVindpm_b:           int   = 0     # 1 = input voltage limit is throttling charge
    chgrThermalReg_b:       int   = 0     # 1 = die thermal regulation active
    chgrWatchdogExpired_b:  int   = 0
    chgrTsStat:             int   = 0     # thermistor zone, see chgrTsStatStr
    chgrTsStatStr:          str   = ""
    chgrVbusOvp_b:          int   = 0     # fault: input over-voltage
    chgrThermalShutdown_b:  int   = 0     # fault: die thermal shutdown
    chgrSafetyTimerExpired_b: int = 0     # fault: charge safety timer expired
    chgrFlagIindpm_b:       int   = 0     # chgrFlag*: event happened since the previous poll
    chgrFlagVindpm_b:       int   = 0
    chgrFlagThermalReg_b:   int   = 0
    chgrFlagWatchdog_b:     int   = 0
    chgrFlagChargeStat_b:   int   = 0
    chgrFlagPowerGood_b:    int   = 0
    chgrFlagVbusStat_b:     int   = 0
    chgrFlagTsStat_b:       int   = 0
    chgrFlagIco_b:          int   = 0
    chgrFlagVbusOvp_b:      int   = 0
    chgrFlagThermalShutdown_b: int = 0
    chgrFlagSafetyTimer_b:  int   = 0
    chgrIbus_a:             float = 0.0   # USB input current [A]
    chgrIchg_a:             float = 0.0   # battery charge current [A]
    chgrVbus_v:             float = 0.0   # USB input voltage [V]
    chgrVbat_v:             float = 0.0   # pack voltage [V]
    chgrVcellTop_v:         float = 0.0   # top cell voltage [V]
    chgrVcellBot_v:         float = 0.0   # bottom cell voltage [V]
    chgrTs_pct:             float = 0.0   # thermistor as % of REGN
    chgrTdie_c:             float = 0.0   # charger die temperature [C]
    chgrCbActive_b:         int   = 0     # cell balancing active
    chgrCbTopCv_b:          int   = 0     # top cell balancing FET in CV mode
    chgrCbBotCv_b:          int   = 0     # bottom cell balancing FET in CV mode
    chgrCbTopOv_b:          int   = 0     # top cell over-voltage
    chgrCbBotOv_b:          int   = 0     # bottom cell over-voltage
    chgrCbOverCurrent_b:    int   = 0     # cell balancing over-current protection active
    chgrFlagCb_b:           int   = 0
    chgrFlagCbTopCv_b:      int   = 0
    chgrFlagCbBotCv_b:      int   = 0
    chgrFlagCbTopOv_b:      int   = 0
    chgrFlagCbBotOv_b:      int   = 0
    chgrFlagCbOverCurrent_b: int  = 0

    # Switch-panel commands live in serial_writer.gndTelem (*Cmd_b).

    # GPS (MAX-M10S, via NMEA GGA/RMC)
    gpsFixValid_b:      int   = 0     # True once a GGA/RMC sentence reports a valid fix
    gpsLat:             float = 0.0   # signed decimal degrees, +N/-S
    gpsLon:             float = 0.0   # signed decimal degrees, +E/-W
    gpsAlt_ft:          float = 0.0   # altitude above mean sea level, from GGA [ft]
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

@dataclass      
class ECURadioTelem:
    header:                 int   = 43962
    packet:                 bytes = field(default_factory=bytes)
    timestamp:              int   = 0
    ecuStatus_e:            int   = 0
    pt1:                    float = 0.0
    pt2:                    float = 0.0
    pt3:                    float = 0.0
    pt4:                    float = 0.0
    rssi:                   int   = 0
    boardTemp_c:            float = 0.0 # temp of the Engine control unit
    battery_V:              float = 0.0
    batteryCurrent_A:       float = 0.0
    altitude_ft:            int   = 0
    verticalVelocity_fps:   int   = 0
    maxVel_fps:             int   = 0
    maxMach:                int   = 0
    maxAlt_ft:              int   = 0
    maxG:                   int   = 0
    gpsFixValid_b:          int   = 0     # True once a GGA/RMC sentence reports a valid fix
    gpsLat_deg:             float = 0.0   # signed decimal degrees, +N/-S
    gpsLon_deg:             float = 0.0   # signed decimal degrees, +E/-W
    gpsAlt_ft:              float = 0.0   # altitude above mean sea level, from GGA [ft]
    gpsNumSV:               int   = 0     # satellites in use, from GGA
    gpsHDOP:                float = 0.0   # horizontal dilution of precision, from GGA
    
    # ecuStatus_e bit field enumeration:
    fillVlvStatus_b:        int   = 0 # b0,  1 = valve open, 0 = valve closed
    ventVlvStatus_b:        int   = 0 # b1,  1 = valve open, 0 = valve closed
    movVlvStatus_b:         int   = 0 # b2,  1 = valve open, 0 = valve closed
    spareVlvStatus_b:       int   = 0 # b3,  1 = valve open, 0 = valve closed
    radioEnableStatus_b:    int   = 0 # b4,  1 = On, 0 = off
    cameraEnableStatus_b:   int   = 0 # b5,  1 = On, 0 = off
    autoFireEnableStatus_b: int   = 0 # b6,  1 = On, 0 = off
    recordEnableStatus_b:   int   = 0 # b7,  1 = On, 0 = off
    spare1EnableStatus_b:   int   = 0 # b8,  1 = On, 0 = off
    spare2EnableStatus_b:   int   = 0 # b9,  1 = On, 0 = off
    armStatus_b:            int   = 0 # b10, 1 = Arm, 0 = Safe
    pyroFireStatus_b:       int   = 0 # b11, 1 = Fire, 0 = off
    pyroChannelStatus_b:    int   = 0 # b12, 1 = Channel 1, 0 = Channel 2
    pwrGoodStatus_b:        int   = 0 # b13, 1 = Good 1, 0 = Bad
    propGoodStatus_b:       int   = 0 # b14, 1 = Good 1, 0 = Bad
    navGoodStatus_b:        int   = 0 # b15, 1 = Good 1, 0 = Bad

    def readBuffer(self):
        # ECU -> ground station, telemetry frame (AB CD) ID ECU_TELEM_ID,
        # 77-byte payload, little-endian, packed. Matches ECU_Payload in
        # tools/switch_packet_test.
        (self.timestamp,                # uint32 ms
        self.ecuStatus_e,               # uint16 bitfield
        self.pt1,
        self.pt2,
        self.pt3,
        self.pt4,
        self.rssi,                      # int8 dBm
        self.boardTemp_c,
        self.battery_V,
        self.batteryCurrent_A,
        self.altitude_ft,               # int32
        self.verticalVelocity_fps,
        self.maxVel_fps,
        self.maxMach,
        self.maxAlt_ft,
        self.maxG,
        self.gpsFixValid_b,             # uint8
        self.gpsLat_deg,                # float32: ~1 m resolution at these latitudes
        self.gpsLon_deg,
        self.gpsAlt_ft,
        self.gpsNumSV,                  # uint8
        self.gpsHDOP) = struct.unpack_from("<IHffffbfffiiiiiiBfffBf", bytes(self.packet))

        self.fillVlvStatus_b        = (self.ecuStatus_e >> 0)  & 1
        self.ventVlvStatus_b        = (self.ecuStatus_e >> 1)  & 1
        self.movVlvStatus_b         = (self.ecuStatus_e >> 2)  & 1
        self.spareVlvStatus_b       = (self.ecuStatus_e >> 3)  & 1
        self.radioEnableStatus_b    = (self.ecuStatus_e >> 4)  & 1
        self.cameraEnableStatus_b   = (self.ecuStatus_e >> 5)  & 1
        self.autoFireEnableStatus_b = (self.ecuStatus_e >> 6)  & 1
        self.recordEnableStatus_b   = (self.ecuStatus_e >> 7)  & 1
        self.spare1EnableStatus_b   = (self.ecuStatus_e >> 8)  & 1
        self.spare2EnableStatus_b   = (self.ecuStatus_e >> 9)  & 1
        self.armStatus_b            = (self.ecuStatus_e >> 10) & 1
        self.pyroFireStatus_b       = (self.ecuStatus_e >> 11) & 1
        self.pyroChannelStatus_b    = (self.ecuStatus_e >> 12) & 1
        self.pwrGoodStatus_b        = (self.ecuStatus_e >> 13) & 1
        self.propGoodStatus_b       = (self.ecuStatus_e >> 14) & 1
        self.navGoodStatus_b        = (self.ecuStatus_e >> 15) & 1

ecuTelem = ECURadioTelem()
ecu_last_rx = 0.0   # time.monotonic() of the last good ECU packet


def ecu_link_ok():
    """True while ECU packets are still arriving (within ECU_LINK_TIMEOUT_S)."""
    return time.monotonic() - ecu_last_rx < ECU_LINK_TIMEOUT_S


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
    global ecu_last_rx
    while True:
        try:
            resp_id, length, payload, crc_b = telem_queue.get()
            if resp_id == ECU_TELEM_ID:
                ecuTelem.packet = payload
                ecuTelem.readBuffer()
                ecu_last_rx = time.monotonic()
                continue

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

# ---------------- LEDs ----------------
def update_indicators():
    """THE place to decide what every LED shows -- both the physical
    switch-panel LEDs and the "LEDs" drawn in the GUI. Called from
    sensor_loop several times a second; just set each one from whatever
    should drive it:

        set_led("LED_NAME", condition)                    # switch panel (TCA9555 output name)
        set_gui_led("NAME", condition, cmd=condition)     # GUI LED (key in settings.led_panel_states)

    Both only do work when the value actually changes, so call them freely.
    Feedback comes from ecuTelem, switch commands from sw.gndTelem.
    """
    # Once ECU packets stop (e.g. radio commanded off), its last packet is
    # stale -- show all feedback as off instead of frozen at the last value.
    ecu = ecuTelem if ecu_link_ok() else ECURadioTelem()
    gnd = sw.gndTelem

    # Switch panel
    set_led("LED_FILL",      ecu.fillVlvStatus_b)
    set_led("LED_VENT",      ecu.ventVlvStatus_b)
    set_led("LED_MOV",       ecu.movVlvStatus_b)
    set_led("LED_SPARE_VLV", ecu.spareVlvStatus_b)
    set_led("LED_ARM",       ecu.armStatus_b)

    # GUI valve LEDs (centre = feedback, border = switch command)
    set_gui_led("FILL", ecu.fillVlvStatus_b, cmd=gnd.fillVlvCmd_b)
    set_gui_led("VENT", ecu.ventVlvStatus_b, cmd=gnd.ventVlvCmd_b)
    set_gui_led("MOV",  ecu.movVlvStatus_b,  cmd=gnd.movVlvCmd_b)

    # GUI status LEDs (settings.status_leds)
    set_gui_led("CAMERA_ON", ecu.cameraEnableStatus_b)
    set_gui_led("AUTO_FIRE", ecu.autoFireEnableStatus_b)
    set_gui_led("PYRO_CH",   ecu.pyroChannelStatus_b)   # on = "PYRO 1", off = "PYRO 2"
    set_gui_led("RADIO_ON",  ecu.radioEnableStatus_b)
    set_gui_led("PWR_GOOD",     ecu.pwrGoodStatus_b)
    set_gui_led("PROP_GOOD",    ecu.propGoodStatus_b)
    set_gui_led("NAV_GOOD",     ecu.navGoodStatus_b)
    set_gui_led("STATION_GOOD", station_good())

# TO DO =================
def station_good():
    """1 if the ground station itself is healthy. Placeholder -- always 1
    for now; add the real checks here (station battery, CPU temp, IO
    expanders responding, ...)."""
    return 1


_leds_written = {}   # panel LED signal -> last level successfully written
_led_errors = set()  # panel LED signals whose last write failed (report once)

def set_led(signal, on):
    """Drive a switch-panel LED (any TCA9555 output, by its settings name).
    Only touches I2C when the level changes, and a failed write is retried
    on the next call. Signals not on an enabled chip are ignored."""
    on = int(bool(on))
    if _leds_written.get(signal) == on:
        return
    try:
        snsrs.io_write(signal, on)
    except KeyError:
        return
    except Exception as e:
        if signal not in _led_errors:
            print(f"LED {signal} write error:", e)
            _led_errors.add(signal)
        return
    _led_errors.discard(signal)
    _leds_written[signal] = on


gui_leds = {}   # GUI LED name -> (on, cmd); drawn by gui2.update_leds()

def set_gui_led(name, on, cmd=0):
    """Set a GUI LED: `on` lights the centre, `cmd` lights the border in
    color_cmd. `name` is a key in settings.led_panel_states."""
    gui_leds[name] = (int(bool(on)), int(bool(cmd)))


def read_switch(signal):
    """A switch's level from the last IO-expander poll (TCA9555 signal name
    in gui_settings.TCA9555_CHIPS); 0 if its chip isn't responding or the
    signal isn't on an enabled chip."""
    try:
        return snsrs.io_cached(signal) or 0
    except KeyError:
        return 0


def read_switch_commands():
    """Copy the switch panel into the ground station payload (sw.gndTelem)."""
    gnd = sw.gndTelem
    gnd.fillVlvCmd_b        = read_switch("SW_FILL")
    gnd.ventVlvCmd_b        = read_switch("SW_VENT")
    gnd.movVlvCmd_b         = read_switch("SW_MOV")
    gnd.spareVlvCmd_b       = read_switch("SW_SPARE_VLV")
    gnd.radioEnableCmd_b    = read_switch("SW_TM_EN")
    gnd.cameraEnableCmd_b   = read_switch("SW_CAMERA_EN")
    gnd.autoFireEnableCmd_b = read_switch("SW_AUTO_FIRE_EN")
    gnd.recordEnableCmd_b   = read_switch("SW_REC_EN")
    gnd.spare1EnableCmd_b   = read_switch("SW_SPARE1")
    gnd.spare2EnableCmd_b   = read_switch("SW_SPARE2")
    gnd.armCmd_b            = read_switch("SW_ARM")
    gnd.pyroFireCmd_b       = read_switch("SW_PYRO_FIRE")
    gnd.pyroChannel_b       = read_switch("SW_PYRO_CH")

# Named input pins on these chips call on_switch_change() when they flip.
SWITCH_EVENT_CHIPS = ("IOX1", "IOX2")


def on_switch_change(signal, state):
    """Called from sensor_loop whenever a switch on SWITCH_EVENT_CHIPS changes.
    signal = settings signal name, state = new level (1 = switch on, after
    the pin's polarity inversion). Runs on the sensor thread, so keep it
    quick -- anything slow should be handed off to another thread."""
    print(f"[SWITCH] {signal} -> {'ON' if state else 'OFF'}")

    if signal == "SW_ARM":
        pass  # TODO: arm (1) / safe (0)
    elif signal == "SW_PYRO_FIRE":
        pass  # TODO: fire the selected pyro channel on 1
    elif signal == "SW_PYRO_CH":
        pass  # TODO: select pyro channel (1 = channel 1, 0 = channel 2)
    elif signal == "SW_REC_EN":
        pass  # TODO: start (1) / stop (0) recording
    elif signal == "SW_CAMERA_EN":
        pass  # TODO: camera on (1) / off (0)
    elif signal == "SW_AUTO_FIRE_EN":
        pass  # TODO: enable (1) / disable (0) auto fire
    elif signal == "SW_TM_EN":
        # Enable radio power if switch is enabled
        snsrs.gpio_write("RADIO_EN", state)
    elif signal == "SW_SPARE1":
        pass
    elif signal == "SW_SPARE2":
        pass


def check_switch_events(last):
    """Call on_switch_change() for every SWITCH_EVENT_CHIPS switch whose
    level differs from `last` (signal -> level, updated in place). The first
    reading of each switch only sets the baseline, so switches already on at
    startup don't fire. A chip that isn't responding is skipped, and its
    switches are compared against their last good level when it's back."""
    for chip in SWITCH_EVENT_CHIPS:
        if chip not in snsrs.io_expanders:
            continue
        for p in settings.TCA9555_CHIPS[chip]["pins"].values():
            signal = p["name"]
            if p["mode"] != "in" or not signal:
                continue
            state = snsrs.io_cached(signal)
            if state is None:
                continue
            prev = last.get(signal)
            last[signal] = state
            if prev is not None and state != prev:
                try:
                    on_switch_change(signal, state)
                except Exception as e:
                    print(f"Switch handler error ({signal}):", e)

def sensor_loop():
    lastTimeINA = 0
    lastTimeChgr = 0
    lastTimeIox = 0
    lastTimeIoxRead = 0
    chgrOk = True   # only report charger errors on the ok -> failing transition, not every poll
    switchLevels = {}       # IOX1/IOX2 switch signal -> last level seen (check_switch_events)
    lastSwitchBits = None   # last commands_e sent on the radio link
    lastSwitchTx = 0
    lastSOC = 100 # update to read from memory or text file
    while True:
        try:
            startSensorLoopTime = time.time()
            # bme280/ads1115 share one Blinka i2c object across threads -- lock
            # it for the duration of these reads so transactions can't interleave.
            with snsrs.i2c_lock:
                streamTelem.stationTemp_c = snsrs.bme280.temperature
                streamTelem.stationBaroAlt_m = snsrs.bme280.altitude

                streamTelem.stationADCChargeVolts = snsrs.vusb_mon_v.voltage * 1.67727393264
                streamTelem.stationADCBattVolts = snsrs.batt_mon_v.voltage * 2.97230769231
                streamTelem.stationADCRadioVolts = snsrs.radio_mon_v.voltage * 2.97230769231

            
            if startSensorLoopTime - lastTimeINA > 1/settings.inaSampleRate:
                # ina219 is on its own separate smbus handle, not the shared i2c bus.
                streamTelem.stationInaBattCurrent = snsrs.ina.current() / 1000
                streamTelem.stationInaBattPower = snsrs.ina.power() / 1000
                streamTelem.stationInaBattVolts = snsrs.ina.voltage()

                #streamTelem.stationInaBattSOC = lastSOC - (streamTelem.stationInaBattSOC*((startSensorLoopTime - lastTimeINA)/3600)/(settings.batt_size_mah/1000))
                streamTelem.stationInaBattSOC = lipo_2s_percent(streamTelem.stationADCBattVolts)
                
                lastTimeINA = time.time()

        except Exception as e:
            print("Sensor error:", e)

        # Separate try so a missing/failing charger doesn't stop the other sensors.
        if snsrs.charger and time.time() - lastTimeChgr > settings.BQ25887_POLL_INTERVAL_S:
            lastTimeChgr = time.time()
            try:
                for name, value in snsrs.charger.poll().items():
                    setattr(streamTelem, name, value)
                streamTelem.stationCharging_b = streamTelem.chgrCharging_b
                if not chgrOk:
                    print("Charger reconnected")
                    chgrOk = True
            except Exception as e:
                streamTelem.chgrConnected_b = 0
                snsrs.charger.applied = False  # re-write settings once it answers again
                if chgrOk:
                    print("Charger error (will keep retrying quietly):", e)
                    chgrOk = False

        # Re-init any I/O expander that failed at startup or has reset since.
        if snsrs.io_expanders and time.time() - lastTimeIox > settings.TCA9555_POLL_INTERVAL_S:
            lastTimeIox = time.time()
            snsrs.check_io_expanders()
        if snsrs.io_expanders and time.time() - lastTimeIoxRead > settings.TCA9555_READ_INTERVAL_S:
            lastTimeIoxRead = time.time()
            snsrs.poll_io_expanders()
            read_switch_commands()
            check_switch_events(switchLevels)

        # Runs even with no IO expanders, so the GUI LEDs still update. A
        # mistake in update_indicators() shouldn't take down sensor_loop.
        try:
            update_indicators()
        except Exception as e:
            print("update_indicators error:", e)

        # Ground station telemetry (switch commands) out on the radio link: on
        # any change, else every SWITCH_PACKET_INTERVAL_S. A switch whose chip
        # isn't answering reads 0.
        if settings.SWITCH_PACKET_ENABLED:
            sw.gndTelem.createPayload()   # refreshes commands_e from the *_b fields
            now = time.time()
            if sw.gndTelem.commands_e != lastSwitchBits or now - lastSwitchTx >= settings.SWITCH_PACKET_INTERVAL_S:
                if sw.send_gnd_telem():
                    lastSwitchBits, lastSwitchTx = sw.gndTelem.commands_e, now


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
                setfield("gpsAlt_ft", parsed.alt*3.28084 if parsed.alt != "" else "")
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
                snsrs.buzzer.change_duty_cycle(0)
                time.sleep(settings.BUZZER_INTERVAL_S)
                continue

            snsrs.buzzer.change_duty_cycle(50)  # 50% duty square wave at BUZZER_FREQUENCY_HZ -> audible tone
            time.sleep(settings.BUZZER_ON_DURATION_S)
            snsrs.buzzer.change_duty_cycle(0)
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