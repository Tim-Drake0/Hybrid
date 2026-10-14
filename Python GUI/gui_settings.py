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

LED_W = 130
LED_H = 120
LED_SPACING_X = 10
LED_SPACING_Y = 10
LED_COLS = 1

led_panel_states = {
    "FILL":   {"state": 0, "color_on": (0, 200, 255),   "color_off": (0, 40, 60),  "label_on": "OPEN",   "label_off": "CLOSED"},
    "VENT":   {"state": 0, "color_on": (0, 200, 255),   "color_off": (0, 40, 60),  "label_on": "OPEN",   "label_off": "CLOSED"},
    "MOV":    {"state": 0, "color_on": (0, 200, 255),   "color_off": (0, 40, 60),  "label_on": "OPEN",   "label_off": "CLOSED"},
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
BUZZER_GPIO_PIN = 13
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
    
