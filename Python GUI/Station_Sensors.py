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


# ---------------- BQ25887 2S charger (I2C) ----------------
class BQ25887:
    """Driver for the TI BQ25887 2-cell boost charger (datasheet SLUSD89B).

    apply_settings() writes gui_settings.BQ25887_SETTINGS (real units) to the
    chip. poll() kicks the I2C watchdog, re-applies the settings if the chip
    has reset them (watchdog expiry, brown-out, ...), and returns every
    readable status/flag/ADC value as a dict keyed by streamTelem field name.

    Own smbus2 handle like the GPS, and only ever called from sensor_loop,
    so it doesn't need i2c_lock.
    """

    # (reg, shift, width) for every configurable field.
    _FIELDS = {
        "VCELLREG":       (0x00, 0, 8),
        "EN_HIZ":         (0x01, 7, 1), "EN_ILIM":       (0x01, 6, 1), "ICHG":        (0x01, 0, 6),
        "EN_VINDPM_RST":  (0x02, 7, 1), "EN_BAT_DISCHG": (0x02, 6, 1), "PFM_OOA_DIS": (0x02, 5, 1), "VINDPM": (0x02, 0, 5),
        "EN_ICO":         (0x03, 5, 1), "IINDPM":        (0x03, 0, 5),
        "IPRECHG":        (0x04, 4, 4), "ITERM":         (0x04, 0, 4),
        "EN_TERM":        (0x05, 7, 1), "STAT_DIS":      (0x05, 6, 1), "WATCHDOG":    (0x05, 4, 2),
        "EN_TIMER":       (0x05, 3, 1), "CHG_TIMER":     (0x05, 1, 2), "TMR2X_EN":    (0x05, 0, 1),
        "AUTO_INDET_EN":  (0x06, 6, 1), "TREG":          (0x06, 4, 2), "EN_CHG":      (0x06, 3, 1),
        "CELLLOWV":       (0x06, 2, 1), "VCELL_RECHG":   (0x06, 0, 2),
        "PFM_DIS":        (0x07, 7, 1), "TOPOFF_TIMER":  (0x07, 4, 2),
        "JEITA_VSET":     (0x08, 3, 2), "JEITA_ISETH":   (0x08, 2, 1), "JEITA_ISETC": (0x08, 0, 2),
        "ADC_DONE_MASK":  (0x12, 7, 1), "IINDPM_MASK":   (0x12, 6, 1), "VINDPM_MASK": (0x12, 5, 1),
        "TREG_MASK":      (0x12, 4, 1), "WD_MASK":       (0x12, 3, 1), "CHRG_MASK":   (0x12, 0, 1),
        "PG_MASK":        (0x13, 7, 1), "VBUS_MASK":     (0x13, 4, 1), "TS_MASK":     (0x13, 2, 1), "ICO_MASK": (0x13, 1, 1),
        "VBUS_OVP_MASK":  (0x14, 7, 1), "TSHUT_MASK":    (0x14, 6, 1), "TMR_MASK":    (0x14, 4, 1), "SNS_SHORT_MASK": (0x14, 3, 1),
        "ADC_EN":         (0x15, 7, 1), "ADC_RATE":      (0x15, 6, 1), "ADC_SAMPLE":  (0x15, 4, 2),
        "IBUS_ADC_DIS":   (0x16, 7, 1), "ICHG_ADC_DIS":  (0x16, 6, 1), "VBUS_ADC_DIS": (0x16, 5, 1), "VBAT_ADC_DIS": (0x16, 4, 1),
        "TS_ADC_DIS":     (0x16, 2, 1), "VCELL_ADC_DIS": (0x16, 1, 1), "TDIE_ADC_DIS": (0x16, 0, 1),
        "VDIFF_END_OFFSET": (0x28, 5, 3), "TCB_QUAL_INTERVAL": (0x28, 4, 1), "TCB_ACTIVE": (0x28, 2, 2), "TSETTLE": (0x28, 0, 2),
        "VQUAL_TH":       (0x29, 4, 4), "VDIFF_START":   (0x29, 0, 4),
        "CB_CHG_DIS":     (0x2A, 7, 1), "CB_AUTO_EN":    (0x2A, 6, 1),
        "QCBH_EN":        (0x2B, 7, 1), "QCBL_EN":       (0x2B, 6, 1),
        "CB_MASK":        (0x2C, 5, 1), "HS_CV_MASK":    (0x2C, 4, 1), "LS_CV_MASK":  (0x2C, 3, 1),
        "HS_OV_MASK":     (0x2C, 2, 1), "LS_OV_MASK":    (0x2C, 1, 1), "CB_OC_MASK":  (0x2C, 0, 1),
    }

    # settings key -> mask field
    _MASKS = {
        "mask_adc_done": "ADC_DONE_MASK", "mask_iindpm": "IINDPM_MASK", "mask_vindpm": "VINDPM_MASK",
        "mask_treg": "TREG_MASK", "mask_watchdog": "WD_MASK", "mask_chrg": "CHRG_MASK",
        "mask_pg": "PG_MASK", "mask_vbus": "VBUS_MASK", "mask_ts": "TS_MASK", "mask_ico": "ICO_MASK",
        "mask_vbus_ovp": "VBUS_OVP_MASK", "mask_tshut": "TSHUT_MASK", "mask_timer": "TMR_MASK",
        "mask_sns_short": "SNS_SHORT_MASK", "mask_cb": "CB_MASK", "mask_hs_cv": "HS_CV_MASK",
        "mask_ls_cv": "LS_CV_MASK", "mask_hs_ov": "HS_OV_MASK", "mask_ls_ov": "LS_OV_MASK", "mask_cb_oc": "CB_OC_MASK",
    }

    CHRG_STAT_NAMES = ["Not charging", "Trickle", "Pre-charge", "Fast (CC)", "Taper (CV)", "Top-off", "Done", "Reserved"]
    VBUS_STAT_NAMES = ["No input", "USB SDP", "USB CDP (1.5A)", "Adapter (3A)", "Poor source",
                       "Unknown (500mA)", "Non-standard", "Reserved"]
    ICO_STAT_NAMES  = ["Disabled", "Optimizing", "Max current found", "Reserved"]
    TS_STAT_NAMES   = {0: "Normal", 2: "Warm", 3: "Cool", 5: "Cold", 6: "Hot"}

    REG_WD_RST = 0x07
    WD_RST_BIT = 1 << 6

    def __init__(self, bus_num, address, cfg):
        self._bus = SMBus(bus_num)
        self._address = address
        self._fields = self.encode_settings(cfg)  # validate up front so a bad settings file fails loudly
        self._one_shot_adc = cfg["adc_enabled"] and not cfg["adc_continuous"]
        self.applied = False
        self.reapply_count = 0

    # ---- settings -> register fields ----
    @staticmethod
    def _range(cfg, key, lo, hi, step, offset=None):
        val = cfg[key]
        if not lo <= val <= hi:
            raise ValueError(f"BQ25887_SETTINGS['{key}'] = {val} is outside {lo}..{hi}")
        return round((val - (lo if offset is None else offset)) / step)

    @staticmethod
    def _choice(cfg, key, options):
        val = cfg[key]
        if val not in options:
            raise ValueError(f"BQ25887_SETTINGS['{key}'] = {val!r}, must be one of {list(options)}")
        return options[val]

    @classmethod
    def encode_settings(cls, cfg):
        """Settings dict (real units) -> {field name: raw code}. Raises
        ValueError naming the offending key if anything is out of range."""
        r, c = cls._range, cls._choice
        if (cfg["cb_manual_discharge_top"] or cfg["cb_manual_discharge_bottom"]) and cfg["cb_auto_enabled"]:
            raise ValueError("BQ25887_SETTINGS: manual cell discharge requires cb_auto_enabled = False")
        if cfg["cb_end_offset_mv"] >= cfg["cb_start_threshold_mv"]:
            raise ValueError("BQ25887_SETTINGS: cb_end_offset_mv must be less than cb_start_threshold_mv")
        f = {
            "VCELLREG":      r(cfg, "cell_charge_voltage_v", 3.40, 4.60, 0.005),
            "ICHG":          r(cfg, "charge_current_ma", 100, 2200, 50, offset=0),
            "IPRECHG":       r(cfg, "precharge_current_ma", 50, 800, 50),
            "ITERM":         r(cfg, "termination_current_ma", 50, 800, 50),
            "VCELL_RECHG":   c(cfg, "recharge_offset_mv", {50: 0, 100: 1, 150: 2, 200: 3}),
            "CELLLOWV":      c(cfg, "precharge_to_fast_v", {2.8: 0, 3.0: 1}),
            "EN_TERM":       int(bool(cfg["termination_enabled"])),
            "TOPOFF_TIMER":  c(cfg, "topoff_timer_min", {0: 0, 15: 1, 30: 2, 45: 3}),

            "VINDPM":        r(cfg, "input_voltage_limit_v", 3.9, 5.5, 0.1),
            "EN_VINDPM_RST": int(bool(cfg["input_voltage_limit_reset_on_plugin"])),
            "IINDPM":        r(cfg, "input_current_limit_ma", 500, 3300, 100),
            "EN_ILIM":       int(bool(cfg["ilim_pin_enabled"])),
            "EN_ICO":        int(bool(cfg["ico_enabled"])),
            "AUTO_INDET_EN": int(bool(cfg["auto_input_detect_enabled"])),

            "EN_CHG":        int(bool(cfg["charge_enabled"])),
            "EN_HIZ":        int(bool(cfg["hiz_enabled"])),
            "STAT_DIS":      int(not cfg["stat_pin_enabled"]),
            "PFM_DIS":       int(not cfg["pfm_enabled"]),
            "PFM_OOA_DIS":   int(not cfg["pfm_out_of_audio_enabled"]),
            "EN_BAT_DISCHG": int(bool(cfg["bat_discharge_load_enabled"])),

            "WATCHDOG":      c(cfg, "watchdog_s", {0: 0, 40: 1, 80: 2, 160: 3}),
            "EN_TIMER":      int(bool(cfg["safety_timer_enabled"])),
            "CHG_TIMER":     c(cfg, "safety_timer_hr", {5: 0, 8: 1, 12: 2, 20: 3}),
            "TMR2X_EN":      int(bool(cfg["safety_timer_2x_in_dpm"])),

            "TREG":          c(cfg, "thermal_regulation_c", {60: 0, 80: 1, 100: 2, 120: 3}),
            "JEITA_VSET":    c(cfg, "jeita_warm_voltage", {"suspend": 0, "8.0V": 1, "8.3V": 2, "unchanged": 3}),
            "JEITA_ISETH":   c(cfg, "jeita_warm_current_pct", {40: 0, 100: 1}),
            "JEITA_ISETC":   c(cfg, "jeita_cool_current_pct", {0: 0, 20: 1, 40: 2, 100: 3}),

            "ADC_EN":        int(bool(cfg["adc_enabled"])),
            "ADC_RATE":      int(not cfg["adc_continuous"]),
            "ADC_SAMPLE":    c(cfg, "adc_resolution_bits", {15: 0, 14: 1, 13: 2, 12: 3}),
            "IBUS_ADC_DIS":  int(not cfg["adc_ibus_enabled"]),
            "ICHG_ADC_DIS":  int(not cfg["adc_ichg_enabled"]),
            "VBUS_ADC_DIS":  int(not cfg["adc_vbus_enabled"]),
            "VBAT_ADC_DIS":  int(not cfg["adc_vbat_enabled"]),
            "TS_ADC_DIS":    int(not cfg["adc_ts_enabled"]),
            "VCELL_ADC_DIS": int(not cfg["adc_vcell_enabled"]),
            "TDIE_ADC_DIS":  int(not cfg["adc_tdie_enabled"]),

            "CB_AUTO_EN":    int(bool(cfg["cb_auto_enabled"])),
            "CB_CHG_DIS":    int(bool(cfg["cb_charge_pause_for_measure"])),
            "VQUAL_TH":      0b1111 if cfg["cb_qual_threshold_mv"] is None else r(cfg, "cb_qual_threshold_mv", 40, 180, 10),
            "VDIFF_START":   r(cfg, "cb_start_threshold_mv", 40, 190, 10),
            "VDIFF_END_OFFSET": r(cfg, "cb_end_offset_mv", 30, 100, 10),
            "TCB_QUAL_INTERVAL": c(cfg, "cb_qual_interval_min", {2: 0, 4: 1}),
            "TCB_ACTIVE":    c(cfg, "cb_active_interval", {"4s": 0, "32s": 1, "2min": 2, "4min": 3}),
            "TSETTLE":       c(cfg, "cb_settle_time", {"10ms": 0, "100ms": 1, "1s": 2, "2s": 3}),
            "QCBH_EN":       int(bool(cfg["cb_manual_discharge_top"])),
            "QCBL_EN":       int(bool(cfg["cb_manual_discharge_bottom"])),
        }
        for key, field_name in cls._MASKS.items():
            f[field_name] = int(bool(cfg[key]))
        return f

    def _reg_masks(self, skip=()):
        """{reg: (mask, value)} for every configured field, minus `skip`."""
        regs = {}
        for name, code in self._fields.items():
            if name in skip:
                continue
            reg, shift, width = self._FIELDS[name]
            m = ((1 << width) - 1) << shift
            mask, val = regs.get(reg, (0, 0))
            regs[reg] = (mask | m, val | ((code << shift) & m))
        return regs

    # ---- I2C ----
    def _read(self, reg):
        return self._bus.read_byte_data(self._address, reg)

    def _write(self, reg, val):
        self._bus.write_byte_data(self._address, reg, val)

    def _read_all(self):
        # smbus block reads top out at 32 bytes, so 0x00..0x2C takes two.
        return self._bus.read_i2c_block_data(self._address, 0x00, 32) + \
               self._bus.read_i2c_block_data(self._address, 0x20, 13)

    def apply_settings(self):
        """Read-modify-write every configured field (reserved bits are left
        alone), then read back to confirm."""
        for reg, (mask, val) in sorted(self._reg_masks().items()):
            self._write(reg, (self._read(reg) & ~mask) | val)
        bad = self._config_mismatches(self._read_all())
        if bad:
            raise IOError(f"BQ25887: readback mismatch in reg(s) {', '.join(f'0x{r:02X}' for r in bad)}")
        self.applied = True

    def _config_mismatches(self, regs):
        # ADC_EN self-clears after a one-shot conversion, so don't count it.
        skip = ("ADC_EN",) if self._one_shot_adc else ()
        return [reg for reg, (mask, val) in self._reg_masks(skip).items() if regs[reg] & mask != val]

    def read_config(self, regs=None):
        """Current register config as {field name: raw code} (for debugging)."""
        regs = regs or self._read_all()
        return {name: (regs[reg] >> shift) & ((1 << width) - 1)
                for name, (reg, shift, width) in self._FIELDS.items()}

    # ---- polling ----
    @staticmethod
    def _u16(regs, hi):
        return (regs[hi] << 8) | regs[hi + 1]

    @classmethod
    def _s16(cls, regs, hi):
        v = cls._u16(regs, hi)
        return v - 0x10000 if v & 0x8000 else v

    def poll(self):
        """Kick the watchdog, re-apply settings if the chip lost them, and
        return all readable values. The flag registers (0x0F-0x11, 0x2B)
        clear on read, so chgrFlag* values mean "happened since last poll"."""
        if not self.applied:
            self.apply_settings()

        regs = self._read_all()
        if regs[0x0B] & (1 << 3) or self._config_mismatches(regs):
            # Watchdog expired / chip reset: registers are back at defaults.
            self.reapply_count += 1
            self.apply_settings()
            regs = self._read_all()

        self._write(self.REG_WD_RST, regs[self.REG_WD_RST] | self.WD_RST_BIT)
        if self._one_shot_adc:
            self._write(0x15, regs[0x15] | 0x80)  # trigger the next conversion

        b = lambda reg, bit: (regs[reg] >> bit) & 1
        chrg, vbus, ico, ts = regs[0x0B] & 0x7, (regs[0x0C] >> 4) & 0x7, (regs[0x0C] >> 1) & 0x3, regs[0x0D] & 0x7
        return {
            "chgrConnected_b":        1,
            "chgrReapplyCount":       self.reapply_count,
            "chgrPartNum":            (regs[0x25] >> 3) & 0xF,
            "chgrDevRev":             regs[0x25] & 0x7,
            # Status
            "chgrChargeStat":         chrg,
            "chgrChargeStatStr":      self.CHRG_STAT_NAMES[chrg],
            "chgrCharging_b":         int(1 <= chrg <= 5),
            "chgrPowerGood_b":        b(0x0C, 7),
            "chgrVbusStat":           vbus,
            "chgrVbusStatStr":        self.VBUS_STAT_NAMES[vbus],
            "chgrIcoStat":            ico,
            "chgrIcoStatStr":         self.ICO_STAT_NAMES[ico],
            "chgrIcoIlim_ma":         (regs[0x0A] & 0x1F) * 100 + 500,
            "chgrIindpm_b":           b(0x0B, 6),
            "chgrVindpm_b":           b(0x0B, 5),
            "chgrThermalReg_b":       b(0x0B, 4),
            "chgrWatchdogExpired_b":  b(0x0B, 3),
            "chgrTsStat":             ts,
            "chgrTsStatStr":          self.TS_STAT_NAMES.get(ts, "Reserved"),
            # Faults
            "chgrVbusOvp_b":          b(0x0E, 7),
            "chgrThermalShutdown_b":  b(0x0E, 6),
            "chgrSafetyTimerExpired_b": b(0x0E, 4),
            # Flags (latched events since last poll)
            "chgrFlagIindpm_b":       b(0x0F, 6),
            "chgrFlagVindpm_b":       b(0x0F, 5),
            "chgrFlagThermalReg_b":   b(0x0F, 4),
            "chgrFlagWatchdog_b":     b(0x0F, 3),
            "chgrFlagChargeStat_b":   b(0x0F, 0),
            "chgrFlagPowerGood_b":    b(0x10, 7),
            "chgrFlagVbusStat_b":     b(0x10, 4),
            "chgrFlagTsStat_b":       b(0x10, 2),
            "chgrFlagIco_b":          b(0x10, 1),
            "chgrFlagVbusOvp_b":      b(0x11, 7),
            "chgrFlagThermalShutdown_b": b(0x11, 6),
            "chgrFlagSafetyTimer_b":  b(0x11, 4),
            # ADC
            "chgrIbus_a":             self._s16(regs, 0x17) / 1000,
            "chgrIchg_a":             self._s16(regs, 0x19) / 1000,
            "chgrVbus_v":             self._u16(regs, 0x1B) / 1000,
            "chgrVbat_v":             self._u16(regs, 0x1D) / 1000,
            "chgrVcellTop_v":         self._u16(regs, 0x1F) / 1000,
            "chgrVcellBot_v":         self._u16(regs, 0x26) / 1000,
            "chgrTs_pct":             self._s16(regs, 0x21) * 100 / 1024,
            "chgrTdie_c":             self._s16(regs, 0x23) * 0.5,
            # Cell balancing
            "chgrCbActive_b":         b(0x2A, 5),
            "chgrCbTopCv_b":          b(0x2A, 4),
            "chgrCbBotCv_b":          b(0x2A, 3),
            "chgrCbTopOv_b":          b(0x2A, 2),
            "chgrCbBotOv_b":          b(0x2A, 1),
            "chgrCbOverCurrent_b":    b(0x2A, 0),
            "chgrFlagCb_b":           b(0x2B, 5),
            "chgrFlagCbTopCv_b":      b(0x2B, 4),
            "chgrFlagCbBotCv_b":      b(0x2B, 3),
            "chgrFlagCbTopOv_b":      b(0x2B, 2),
            "chgrFlagCbBotOv_b":      b(0x2B, 1),
            "chgrFlagCbOverCurrent_b": b(0x2B, 0),
        }


charger = None
if settings.BQ25887_ENABLED:
    charger = BQ25887(settings.BQ25887_I2C_BUS, settings.BQ25887_I2C_ADDRESS, settings.BQ25887_SETTINGS)