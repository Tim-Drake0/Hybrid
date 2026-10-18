import dearpygui.dearpygui as dpg

WINDOW_POS = (0,0)
WINDOW_DIM = (1920,1020)

TAB_WINDOW_POS = (0,0)
TAB_WINDOW_DIM = (WINDOW_DIM[0],WINDOW_DIM[1]-TAB_WINDOW_POS[1])

# Child window size and positions:
STATUS_BAR_POS = (0, 0)
STATUS_BAR_SIZE = (WINDOW_DIM[0] - 25, 60)



y_offset = 32
x_offset = 5

LED_W = 115
LED_H = 115
LED_SPACING_X = 10
LED_SPACING_Y = 10
LED_COLS = 1

LED_BORDER_THICKNESS = 6

# True = valve "feedback" (LED centres, switch-panel LEDs) just mirrors the
# switch-panel command. Set False once the serial stream reports real valve
# states (fill/vent/mov_state).
VALVE_FEEDBACK_FROM_SWITCHES = True

# Centre = valve feedback from the serial stream (color_on/color_off).
# Border = switch panel command: color_cmd while the switch commands open,
# otherwise the same as the centre.
led_panel_states = {
    "FILL":   {"state": 0, "cmd": 0, "color_on": (0, 200, 255),   "color_off": (0, 40, 60),  "color_cmd": (255, 170, 0),  "label_on": "OPEN",   "label_off": "CLOSED"},
    "VENT":   {"state": 0, "cmd": 0, "color_on": (0, 200, 255),   "color_off": (0, 40, 60),  "color_cmd": (255, 170, 0),  "label_on": "OPEN",   "label_off": "CLOSED"},
    "MOV":    {"state": 0, "cmd": 0, "color_on": (0, 200, 255),   "color_off": (0, 40, 60),  "color_cmd": (255, 170, 0),  "label_on": "OPEN",   "label_off": "CLOSED"},
}

EVENTS_WINDOW_SIZE = (150,400)
EVENTS_WINDOW_POS = (WINDOW_DIM[0] - EVENTS_WINDOW_SIZE[0], STATUS_BAR_SIZE[1] + 10)

INFO_WINDOW_POS = (0, STATUS_BAR_SIZE[1] + 10)
INFO_WINDOW_SIZE = (570, 550)  

ERROR_WINDOW_POS = (0, INFO_WINDOW_POS[1] + INFO_WINDOW_SIZE[1])
ERROR_WINDOW_SIZE = (INFO_WINDOW_SIZE[0], WINDOW_DIM[1]-INFO_WINDOW_SIZE[1]-485)  

PRESS_PLOT_WINDOW_SIZE = (EVENTS_WINDOW_POS[0] - INFO_WINDOW_SIZE[0] + 5, 550) 
PRESS_PLOT_WINDOW_POS = (INFO_WINDOW_SIZE[0] + 5, STATUS_BAR_SIZE[1] + 10)

PLOT_WINDOW_POS = (PRESS_PLOT_WINDOW_POS[0], STATUS_BAR_SIZE[1] + 565)
PLOT_WINDOW_SIZE = (WINDOW_DIM[0]- PRESS_PLOT_WINDOW_POS[0] - 5, ERROR_WINDOW_SIZE[1])  

RIGHT_WINDOWS = [
    "right_window_bus_info",
    "right_window_bme280",
    "right_window_lsm9ds1",
    "right_window_adxl375",
    "right_window_eeprom"
]

# At the top of your file or in an init function, parse the saturation data:
SAT_TEMPS = [
    0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,
    21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,
    41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,
    61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,
    81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97
]
SAT_PRESSURES = [
    278.33,282.88,287.49,292.15,296.87,301.64,306.46,311.35,316.29,321.28,326.34,
    331.45,336.62,341.84,347.13,352.47,357.88,363.34,368.87,374.45,380.10,
    385.81,391.58,397.42,403.32,409.28,415.30,421.39,427.54,433.76,440.05,
    446.40,452.82,459.30,465.86,472.48,479.17,485.93,492.76,499.66,506.62,
    513.65,520.75,527.92,535.16,542.47,549.85,557.30,564.82,572.41,580.08,
    587.82,595.63,603.52,611.48,619.51,627.96,636.45,644.79,653.21,661.71,
    670.30,678.97,687.72,696.56,705.49,714.51,723.61,732.80,742.09,751.46,
    760.93,770.49,780.14,789.89,799.74,809.68,819.72,829.87,840.11,850.46,
    860.92,871.48,882.15,892.93,903.82,914.83,925.96,937.21,948.58,960.08,
    971.72,983.49,995.41,1007.5,1019.7,1032.1,1044.8
]

batt_size_mah = 850


inaSampleRate = 5 #Hz

CPU_TEMP_POLL_INTERVAL_S = 2 # How often to read the ground-station Pi's own CPU temp sensor, in seconds.
CPU_TEMP_WARN_C = 75.0 # Ground-station Pi CPU temp (°C) at/above which a warning row is shown
BUZZER_ENABLED = False
# Buzzer is on GPIO13 using Pi 5 hardware PWM. Requires this line in
# /boot/firmware/config.txt (then reboot):
#   dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
# GPIO12 -> channel 0, GPIO13 -> channel 1. The chip is pwmchip0 on Pi 5
# kernels 6.6.47+ (pwmchip2 on older ones) -- check `ls /sys/class/pwm/`.
BUZZER_PWM_CHIP = 0
BUZZER_PWM_CHANNEL = 1
BUZZER_FREQUENCY_HZ = 4000
BUZZER_ON_DURATION_S = 1.0
BUZZER_INTERVAL_S = 5.0

# ---------------- BQ25887 2S charger (I2C) ----------------
# Written to the chip at startup, and re-applied automatically if the chip's
# I2C watchdog expires or a register no longer matches (the watchdog resets
# most of these to chip defaults). Values are in real units; each is rounded
# to the nearest step the chip supports. Ranges/steps from TI SLUSD89B.
BQ25887_ENABLED          = True
BQ25887_I2C_BUS          = 1
BQ25887_I2C_ADDRESS      = 0x6A
BQ25887_POLL_INTERVAL_S  = 1.0

BQ25887_SETTINGS = {
    # --- Charge limits ---
    "cell_charge_voltage_v":      4.20,   # per cell, 3.40-4.60 V, 5 mV step (pack = 2x)
    "charge_current_ma":          850,    # fast charge, 100-2200 mA, 50 mA step
    "precharge_current_ma":       100,    # 50-800 mA, 50 mA step
    "termination_current_ma":     100,    # 50-800 mA, 50 mA step
    "recharge_offset_mv":         100,    # recharge when cell drops this far below the limit: 50/100/150/200 mV
    "precharge_to_fast_v":        3.0,    # per-cell precharge -> fast charge threshold: 2.8 or 3.0 V
    "termination_enabled":        True,
    "topoff_timer_min":           0,      # extra charging after termination: 0 (off)/15/30/45 min

    # --- Input limits ---
    "input_voltage_limit_v":      4.3,    # VINDPM, 3.9-5.5 V, 100 mV step
    "input_voltage_limit_reset_on_plugin": True,  # chip resets VINDPM to default on adapter plug-in
    "input_current_limit_ma":     2000,   # IINDPM, 500-3300 mA, 100 mA step (actual = lowest of this, ICO, ILIM pin, PSEL)
    "ilim_pin_enabled":           True,   # honor the ILIM pin resistor limit
    "ico_enabled":                True,   # input current optimizer: finds the max the adapter can supply
    "auto_input_detect_enabled":  True,   # PSEL detection when VBUS is plugged in

    # --- On/off control ---
    "charge_enabled":             True,
    "hiz_enabled":                False,  # True = input high-impedance, draw nothing from USB
    "stat_pin_enabled":           True,
    "pfm_enabled":                True,   # light-load PFM mode
    "pfm_out_of_audio_enabled":   True,   # keep PFM switching above audio band
    "bat_discharge_load_enabled": False,  # BAT pin discharge load

    # --- Timers ---
    "watchdog_s":                 40,     # 0 (off)/40/80/160 s; kicked every poll while the GUI runs
    "safety_timer_enabled":       True,
    "safety_timer_hr":            5,     # 5/8/12/20 hr
    "safety_timer_2x_in_dpm":     True,   # safety timer runs at half speed during DPM / thermal regulation

    # --- Temperature ---
    "thermal_regulation_c":       120,    # die temp regulation: 60/80/100/120 C
    "jeita_warm_voltage":         "8.0V", # 45-60 C pack voltage: "suspend" / "8.0V" / "8.3V" / "unchanged"
    "jeita_warm_current_pct":     100,    # 45-60 C charge current: 40 or 100 % of charge_current_ma
    "jeita_cool_current_pct":     20,     # 0-10 C charge current: 0 (suspend)/20/40/100 %

    # --- ADC ---
    "adc_enabled":                True,
    "adc_continuous":             True,   # False = one-shot (re-triggered each poll)
    "adc_resolution_bits":        15,     # 15/14/13/12 effective bits (lower = faster)
    "adc_ibus_enabled":           True,
    "adc_ichg_enabled":           True,
    "adc_vbus_enabled":           True,
    "adc_vbat_enabled":           True,
    "adc_ts_enabled":             True,   # costs extra battery current when on battery only
    "adc_vcell_enabled":          True,
    "adc_tdie_enabled":           True,

    # --- Cell balancing ---
    "cb_auto_enabled":            True,   # must be False to use the manual discharge switches below
    "cb_charge_pause_for_measure": True,  # pause charging while measuring cell voltages (more accurate)
    "cb_qual_threshold_mv":       None,   # pre-qualification -> qualification: 40-180 mV, 10 mV step; None = skip pre-qual
    "cb_start_threshold_mv":      80,     # cell difference to start balancing: 40-190 mV, 10 mV step
    "cb_end_offset_mv":           40,     # stop balancing at start - this: 30-100 mV, 10 mV step
    "cb_qual_interval_min":       2,      # 2 or 4 min between pre-qualification measurements
    "cb_active_interval":         "2min", # time between measurements while balancing: "4s"/"32s"/"2min"/"4min"
    "cb_settle_time":             "1s",   # charge-off delay before measuring: "10ms"/"100ms"/"1s"/"2s"
    "cb_manual_discharge_top":    False,  # manual QCBH (top cell) discharge, needs cb_auto_enabled=False
    "cb_manual_discharge_bottom": False,  # manual QCBL (bottom cell) discharge, needs cb_auto_enabled=False

    # --- INT pin masks (True = don't pulse INT for this event) ---
    "mask_adc_done":    False, "mask_iindpm":   False, "mask_vindpm":   False,
    "mask_treg":        False, "mask_watchdog": False, "mask_chrg":     False,
    "mask_pg":          False, "mask_vbus":     False, "mask_ts":       False,
    "mask_ico":         False, "mask_vbus_ovp": False, "mask_tshut":    False,
    "mask_timer":       False, "mask_sns_short": False,
    "mask_cb":          False, "mask_hs_cv":    False, "mask_ls_cv":    False,
    "mask_hs_ov":       False, "mask_ls_ov":    False, "mask_cb_oc":    False,
}

# ---------------- TCA9555 16-bit I/O expanders (I2C) ----------------
# Written to each chip at startup, and re-applied automatically if a chip
# loses its config (power-on reset puts every pin back to input). Datasheet
# TI SCPS200. Pins are named as on the datasheet: P00-P07 (port 0), P10-P17
# (port 1). Every I/O has a fixed internal 100k pull-up to VCC.
#   "name":   optional signal name, so code can use io_write("FILL_SOL", 1)
#             instead of a chip/pin. Must be unique across all chips.
#   "mode":   "in" or "out"
#   "init":   0/1 level driven at startup (outputs only)
#   "invert": True = input reads back inverted (inputs only)
TCA9555_ENABLED         = True
TCA9555_I2C_BUS         = 1
TCA9555_POLL_INTERVAL_S = 1.0   # how often to check each chip still has its config
TCA9555_READ_INTERVAL_S = 0.1   # how often to read pin states (shown on Debug > IO)

TCA9555_CHIPS = {
    "IOX1": {
        "enabled": True,
        "address": 0x23,   # 0x20-0x27, set by A2/A1/A0
        "pins": {
            "P00": {"name": "LED_ARM",      "mode": "out",  "init": 0, "invert": False},
            "P01": {"name": "",             "mode": "out",  "init": 0, "invert": False},
            "P02": {"name": "SW_ARM",       "mode": "in",   "init": 0, "invert": True},
            "P03": {"name": "",             "mode": "out",  "init": 0, "invert": False},
            "P04": {"name": "SW_PYRO_FIRE", "mode": "in",   "init": 0, "invert": True},
            "P05": {"name": "SW_PYRO_CH",   "mode": "in",   "init": 0, "invert": True},
            "P06": {"name": "",             "mode": "out",  "init": 0, "invert": False},
            "P07": {"name": "",             "mode": "in",   "init": 0, "invert": False},
            "P10": {"name": "",             "mode": "out",  "init": 0, "invert": False},
            "P11": {"name": "SW_REC_EN",    "mode": "in",   "init": 0, "invert": True},
            "P12": {"name": "",             "mode": "out",  "init": 0, "invert": False},
            "P13": {"name": "SW_CAMERA_EN", "mode": "in",   "init": 0, "invert": True},
            "P14": {"name": "",             "mode": "out",  "init": 0, "invert": False},
            "P15": {"name": "SW_SPARE1",    "mode": "in",   "init": 0, "invert": True},
            "P16": {"name": "",             "mode": "out",  "init": 0, "invert": False},
            "P17": {"name": "SW_SPARE2",    "mode": "in",   "init": 0, "invert": True},
        },
    },
    "IOX2": {
        "enabled": True,
        "address": 0x22,
        "pins": {
            "P00": {"name": "",                 "mode": "in",  "init": 0, "invert": False},
            "P01": {"name": "",                 "mode": "in",  "init": 0, "invert": False},
            "P02": {"name": "",                 "mode": "in",  "init": 0, "invert": False},
            "P03": {"name": "",                 "mode": "out", "init": 0, "invert": False},
            "P04": {"name": "LED_MOV",          "mode": "out", "init": 0, "invert": False},
            "P05": {"name": "",                 "mode": "out", "init": 0, "invert": False},
            "P06": {"name": "LED_SPARE_VALVE",  "mode": "out", "init": 0, "invert": False},
            "P07": {"name": "",                 "mode": "out", "init": 0, "invert": False},
            "P10": {"name": "",                 "mode": "in",  "init": 0, "invert": False},
            "P11": {"name": "",                 "mode": "in",  "init": 0, "invert": False},
            "P12": {"name": "",                 "mode": "in",  "init": 0, "invert": False},
            "P13": {"name": "",                 "mode": "in",  "init": 0, "invert": False},
            "P14": {"name": "SW_AUTO_FIRE_EN",  "mode": "in",  "init": 0, "invert": True},
            "P15": {"name": "",                 "mode": "out", "init": 0, "invert": False},
            "P16": {"name": "SW_TM_EN",         "mode": "in",  "init": 0, "invert": True},
            "P17": {"name": "",                 "mode": "out", "init": 0, "invert": False},
        },
    },
    "IOX3": {
        "enabled": True,
        "address": 0x21,
        "pins": {
            "P00": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P01": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P02": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P03": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P04": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P05": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P06": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P07": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P10": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P11": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P12": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P13": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P14": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P15": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P16": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P17": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
        },
    },
    "IOX4": {
        "enabled": True,
        "address": 0x20,
        "pins": {
            "P00": {"name": "LED_VENT",         "mode": "out",  "init": 0, "invert": False},
            "P01": {"name": "",                 "mode": "out",  "init": 0, "invert": False},
            "P02": {"name": "SW_VENT",          "mode": "in",   "init": 0, "invert": True},
            "P03": {"name": "",                 "mode": "out",  "init": 0, "invert": False},
            "P04": {"name": "LED_FILL",         "mode": "out",  "init": 0, "invert": False},
            "P05": {"name": "",                 "mode": "out",  "init": 0, "invert": False},
            "P06": {"name": "SW_FILL",          "mode": "in",   "init": 0, "invert": True},
            "P07": {"name": "",                 "mode": "out",  "init": 0, "invert": False},
            "P10": {"name": "LED_PWR_ON",       "mode": "out",  "init": 1, "invert": False},   # always on while the Pi is up
            "P11": {"name": "",                 "mode": "out",  "init": 0, "invert": False},
            "P12": {"name": "LED_TM_RX",        "mode": "out",  "init": 0, "invert": False},
            "P13": {"name": "",                 "mode": "out",  "init": 0, "invert": False},
            "P14": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P15": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P16": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
            "P17": {"name": "",                 "mode": "in",   "init": 0, "invert": False},
        },
    },
}

GPS_MAPS = [
    {
        "name": "FAR",
        "file": "Assets/FAR_map.jpg",
        "bounds_min": (-117.9075, 35.312778),     # (lon, lat) of bottom-left corner
        "bounds_max": (-117.7125, 35.377778),     # (lon, lat) of top-right corner
    },
    {
        "name": "Lancaster",
        "file": "Assets/Lancaster_map.jpg",
        "bounds_min": (-118.227778, 34.651111),
        "bounds_max": (-118.065556, 34.708056),
    },
]

def show_right_window(tag):
    for window in RIGHT_WINDOWS:
        dpg.hide_item(window)
    dpg.show_item(tag)
    
def createFonts():
    global small, default, medium, large, xl
    with dpg.font_registry():
        small = dpg.add_font("Assets/RobotoMono-Regular.ttf", 14)
        default = dpg.add_font("Assets/RobotoMono-Regular.ttf", 18)
        medium = dpg.add_font("Assets/RobotoMono-Regular.ttf", 25)
        large = dpg.add_font("Assets/RobotoMono-Regular.ttf", 30)
        xl = dpg.add_font("Assets/RobotoMono-Regular.ttf", 40)
    
