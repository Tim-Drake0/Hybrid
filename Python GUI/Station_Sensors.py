import os
import sys
import time
import random
import threading
from pyubx2 import UBXReader, NMEA_PROTOCOL, UBX_PROTOCOL
import gui_settings as settings

# Real station hardware only exists on the Pi. Anywhere else (e.g. a Windows
# dev PC) the sensors, GPS, buzzer, charger and I/O expanders are replaced by
# stand-ins below so the GUI can still be run for basic testing.
ON_PI = sys.platform.startswith("linux") and os.path.exists("/dev/i2c-1")

if ON_PI:
    import board
    from adafruit_bme280 import basic as adafruit_bme280
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    from ina219 import INA219
    from ina219 import DeviceRangeError
    from rpi_hardware_pwm import HardwarePWM
    from smbus2 import SMBus, i2c_msg
else:
    print("Station_Sensors: no Pi I2C bus found -- using simulated station hardware")

# bme280/ads1115 share this `i2c` (Blinka) object and may be accessed from
# different threads, so every transaction through it must be serialized with
# this lock. ina219 and the GPS are each on their own separate smbus handles
# (see below) so they don't need it.
i2c_lock = threading.Lock()

# Define your shunt resistor ohm value and maximum expected current
SHUNT_OHMS = 0.05
MAX_EXPECTED_AMPS = 4

if ON_PI:
    i2c = board.I2C()  # uses board.SCL and board.SDA

    # Passive buzzer: needs a driven square wave (not just DC) to produce a tone.
    # Hardware PWM so the tone stays clean regardless of CPU/GIL load (gpiozero's
    # software PWM jittered at 4 kHz and sounded crackly). Needs the pwm-2chan
    # overlay in /boot/firmware/config.txt -- see BUZZER_PWM_* in gui_settings.
    buzzer = HardwarePWM(pwm_channel=settings.BUZZER_PWM_CHANNEL, hz=settings.BUZZER_FREQUENCY_HZ,
                         chip=settings.BUZZER_PWM_CHIP)
    buzzer.start(0)

    bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)

    ads = ADS.ADS1115(i2c, address=0x49)
    # 2/3 = +/-6.144V, 1 = +/-4.096V, 2 = +/-2.048V
    ads.gain = 1

    # 4. Assign the pin channel (0 corresponds to hardware pin A0)
    vusb_mon_v = AnalogIn(ads, 0)
    batt_mon_v = AnalogIn(ads, 1)
    spare_mon_v = AnalogIn(ads, 2)
    radio_mon_v = AnalogIn(ads, 3)

    ina = INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS, busnum=1, address=0x45)
    ina.configure(ina.RANGE_16V)

else:
    # ---------------- simulated hardware (non-Pi) ----------------
    def _noisy(value, spread):
        return value + random.uniform(-spread, spread)

    class _SimBME280:
        @property
        def temperature(self):
            # Real I2C reads take a few ms; without this sensor_loop would
            # spin a whole CPU core on the PC.
            time.sleep(0.05)
            return _noisy(22.0, 0.2)

        @property
        def altitude(self):
            return _noisy(150.0, 0.5)

    class _SimADC:
        # Raw ADC pin volts; serial_reader scales these by the divider ratios.
        def __init__(self, volts):
            self._volts = volts

        @property
        def voltage(self):
            return _noisy(self._volts, 0.005)

    class _SimINA219:
        def current(self): return _noisy(450.0, 20.0)    # mA
        def power(self):   return _noisy(3400.0, 150.0)  # mW
        def voltage(self): return _noisy(7.6, 0.02)      # V

    class _SimBuzzer:
        def change_duty_cycle(self, duty): pass
        def stop(self): pass

    buzzer = _SimBuzzer()
    bme280 = _SimBME280()
    vusb_mon_v  = _SimADC(2.98)   # ~5.0 V after scaling
    batt_mon_v  = _SimADC(2.56)   # ~7.6 V
    spare_mon_v = _SimADC(0.0)
    radio_mon_v = _SimADC(1.68)   # ~5.0 V
    ina = _SimINA219()


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


class _SimGPSReader:
    """Stand-in for the UBXReader off the Pi: produces no messages, and
    blocks like a real read so gps_loop doesn't spin."""
    def read(self):
        time.sleep(1.0)
        return None, None


if ON_PI:
    gps_stream = I2CGPSStream(1, GPS_I2C_ADDRESS)
    gps_reader = UBXReader(gps_stream, protfilter=NMEA_PROTOCOL | UBX_PROTOCOL)
else:
    gps_reader = _SimGPSReader()


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
if settings.BQ25887_ENABLED and ON_PI:
    charger = BQ25887(settings.BQ25887_I2C_BUS, settings.BQ25887_I2C_ADDRESS, settings.BQ25887_SETTINGS)


# ---------------- TCA9555 16-bit I/O expanders (I2C) ----------------
class TCA9555:
    """Driver for one TI TCA9555 16-bit I/O expander (datasheet SCPS200).

    apply_settings() writes a chip's entry from gui_settings.TCA9555_CHIPS
    (pin direction, startup output level, input polarity). check() re-applies
    it if the chip has lost it (a power-on reset puts every pin back to input
    and clears the outputs). Pins can be addressed by datasheet name ("P03",
    "P14") or by the signal name given in settings.

    Own smbus2 handle like the GPS/charger. Output writes are a
    read-modify-write of a cached latch value, so they're serialized with a
    per-chip lock in case they come from more than one thread.
    """

    # Register pairs: port 0 at the even address, port 1 at the odd one. A
    # 2-byte transfer starting at the port-0 register covers both ports.
    REG_INPUT    = 0x00
    REG_OUTPUT   = 0x02
    REG_POLARITY = 0x04
    REG_CONFIG   = 0x06   # 1 = input (power-on default), 0 = output

    PIN_NAMES = [f"P{port}{bit}" for port in (0, 1) for bit in range(8)]   # index = bit in the 16-bit word

    def __init__(self, name, bus_num, cfg):
        self.name = name
        self._bus = self._open_bus(bus_num)
        self._address = cfg["address"]
        # Validate up front so a bad settings file fails loudly.
        self._config, self._polarity, self._output, self._bits = self.encode_settings(name, cfg)
        self._lock = threading.Lock()
        self.applied = False
        self.reapply_count = 0
        self.state = None   # last read_inputs() word from poll_io_expanders(), None = no response

    # ---- settings -> register words ----
    @classmethod
    def encode_settings(cls, name, cfg):
        """Chip settings -> (config, polarity, output) 16-bit words plus a
        {pin name / signal name: bit} lookup. Raises ValueError naming the
        offending pin if anything is invalid."""
        where = f"TCA9555_CHIPS['{name}']"
        if not 0x20 <= cfg["address"] <= 0x27:
            raise ValueError(f"{where}['address'] = 0x{cfg['address']:02X} is outside 0x20..0x27")
        pins = cfg["pins"]
        unknown = set(pins) - set(cls.PIN_NAMES)
        if unknown:
            raise ValueError(f"{where}: unknown pin(s) {sorted(unknown)}, must be P00-P07 / P10-P17")
        missing = [p for p in cls.PIN_NAMES if p not in pins]
        if missing:
            raise ValueError(f"{where}: missing pin(s) {missing}")

        config = polarity = output = 0
        bits = {}
        for bit, pin in enumerate(cls.PIN_NAMES):
            p = pins[pin]
            if p["mode"] not in ("in", "out"):
                raise ValueError(f"{where}['pins']['{pin}']['mode'] = {p['mode']!r}, must be 'in' or 'out'")
            if p["init"] not in (0, 1):
                raise ValueError(f"{where}['pins']['{pin}']['init'] = {p['init']!r}, must be 0 or 1")
            config   |= (p["mode"] == "in") << bit
            polarity |= bool(p["invert"]) << bit
            output   |= p["init"] << bit
            bits[pin] = bit
            if p["name"]:
                if p["name"] in bits:
                    raise ValueError(f"{where}: signal name {p['name']!r} used on more than one pin")
                bits[p["name"]] = bit
        return config, polarity, output, bits

    # ---- I2C ----
    def _open_bus(self, bus_num):
        return SMBus(bus_num)

    def _read16(self, reg):
        lo, hi = self._bus.read_i2c_block_data(self._address, reg, 2)
        return lo | (hi << 8)

    def _write16(self, reg, val):
        self._bus.write_i2c_block_data(self._address, reg, [val & 0xFF, (val >> 8) & 0xFF])

    def apply_settings(self):
        """Write the output latch first, so pins switching to output come up
        at their configured level instead of glitching, then polarity and
        direction. Read back to confirm."""
        with self._lock:
            self._write16(self.REG_OUTPUT, self._output)
            self._write16(self.REG_POLARITY, self._polarity)
            self._write16(self.REG_CONFIG, self._config)
            got = (self._read16(self.REG_OUTPUT), self._read16(self.REG_POLARITY), self._read16(self.REG_CONFIG))
        if got != (self._output, self._polarity, self._config):
            raise IOError(f"TCA9555 {self.name} @0x{self._address:02X}: readback mismatch "
                          f"(out/pol/cfg wrote {self._output:04X}/{self._polarity:04X}/{self._config:04X}, "
                          f"read {got[0]:04X}/{got[1]:04X}/{got[2]:04X})")
        self.applied = True

    def check(self):
        """Apply settings if never applied, or re-apply (restoring the current
        output states) if the chip's config no longer matches."""
        if not self.applied:
            self.apply_settings()
            return
        with self._lock:
            ok = self._read16(self.REG_CONFIG) == self._config and self._read16(self.REG_POLARITY) == self._polarity
        if not ok:
            self.reapply_count += 1
            self.apply_settings()

    # ---- pin access ----
    def has(self, pin):
        return pin in self._bits

    def _bit(self, pin):
        try:
            return self._bits[pin]
        except KeyError:
            raise KeyError(f"TCA9555 {self.name}: no pin or signal named {pin!r}") from None

    def read_inputs(self):
        """All 16 pins as one word (bit 0 = P00 ... bit 15 = P17), after
        polarity inversion. Output pins read back their driven level."""
        with self._lock:
            return self._read16(self.REG_INPUT)

    def read_pin(self, pin):
        return (self.read_inputs() >> self._bit(pin)) & 1

    def write_pin(self, pin, value):
        bit = self._bit(pin)
        if (self._config >> bit) & 1:
            raise ValueError(f"TCA9555 {self.name}: {pin!r} is configured as an input")
        with self._lock:
            out = (self._output | (1 << bit)) if value else (self._output & ~(1 << bit))
            self._write16(self.REG_OUTPUT, out)
            self._output = out


class _SimTCA9555(TCA9555):
    """In-memory TCA9555 for running off the Pi. Behaves like the real chip
    (registers, polarity inversion, outputs reading back their latch), and
    sim_set_input() stands in for flipping a physical switch."""

    simulated = True

    def _open_bus(self, bus_num):
        # Power-on register defaults: outputs latched high, no inversion, all
        # pins inputs. Every pin idles high from its internal pull-up.
        self._regs = {self.REG_OUTPUT: 0xFFFF, self.REG_POLARITY: 0x0000, self.REG_CONFIG: 0xFFFF}
        self._pin_levels = 0xFFFF
        return None

    def _read16(self, reg):
        if reg == self.REG_INPUT:
            cfg = self._regs[self.REG_CONFIG]
            level = (self._pin_levels & cfg) | (self._regs[self.REG_OUTPUT] & ~cfg & 0xFFFF)
            return level ^ (self._regs[self.REG_POLARITY] & cfg)
        return self._regs[reg]

    def _write16(self, reg, val):
        if reg != self.REG_INPUT:
            self._regs[reg] = val & 0xFFFF

    def sim_set_input(self, pin, value):
        """Set an input pin so it reads back as `value` (after polarity
        inversion), e.g. sim_set_input("SW_FILL", 1) = switch on."""
        bit = self._bit(pin)
        if not (self._config >> bit) & 1:
            raise ValueError(f"TCA9555 {self.name}: {pin!r} is configured as an output")
        level = bool(value) ^ bool((self._polarity >> bit) & 1)
        with self._lock:
            self._pin_levels = (self._pin_levels | (1 << bit)) if level else (self._pin_levels & ~(1 << bit))


io_expanders = {}   # chip name -> TCA9555 (_SimTCA9555 off the Pi)
if settings.TCA9555_ENABLED:
    _enabled = {n: c for n, c in settings.TCA9555_CHIPS.items() if c["enabled"]}
    _addresses = [c["address"] for c in _enabled.values()]
    if len(_addresses) != len(set(_addresses)):
        raise ValueError("TCA9555_CHIPS: two enabled chips share an I2C address")
    _signals = [p["name"] for c in _enabled.values() for p in c["pins"].values() if p["name"]]
    if len(_signals) != len(set(_signals)):
        raise ValueError("TCA9555_CHIPS: a signal name is used on more than one pin")
    for _name, _cfg in _enabled.items():
        io_expanders[_name] = (TCA9555 if ON_PI else _SimTCA9555)(_name, settings.TCA9555_I2C_BUS, _cfg)


def init_io_expanders():
    """Apply settings to every enabled TCA9555. A chip that doesn't answer is
    reported and left with applied = False, so check_io_expanders() retries
    it later instead of stopping startup. Returns {chip name: True/False}."""
    ok = {}
    for name, chip in io_expanders.items():
        try:
            chip.apply_settings()
            ok[name] = True
        except Exception as e:
            chip.applied = False
            ok[name] = False
            print(f"TCA9555 {name} init error:", e)
    return ok


def check_io_expanders():
    """Init any chip that failed to, and re-apply any that has reset since."""
    for name, chip in io_expanders.items():
        try:
            chip.check()
        except Exception as e:
            chip.applied = False
            print(f"TCA9555 {name} error:", e)


def poll_io_expanders():
    """Cache every chip's current pin levels in chip.state (for the Debug >
    IO tab), so the GUI never has to touch I2C itself."""
    for name, chip in io_expanders.items():
        try:
            chip.state = chip.read_inputs()
        except Exception as e:
            if chip.state is not None:   # only report the transition, not every poll
                print(f"TCA9555 {name} read error:", e)
            chip.state = None
            chip.applied = False


def _io_chip_for(signal):
    for chip in io_expanders.values():
        if chip.has(signal):
            return chip
    raise KeyError(f"No TCA9555 pin named {signal!r}")


def io_write(signal, value):
    """Drive an output by its settings signal name, e.g. io_write("FILL_SOL", 1)."""
    _io_chip_for(signal).write_pin(signal, value)


def io_read(signal):
    """Read a pin by its settings signal name."""
    return _io_chip_for(signal).read_pin(signal)


def io_cached(signal):
    """A pin's level from the last poll_io_expanders() (no I2C traffic), or
    None if its chip isn't responding."""
    chip = _io_chip_for(signal)
    return None if chip.state is None else (chip.state >> chip._bit(signal)) & 1


init_io_expanders()