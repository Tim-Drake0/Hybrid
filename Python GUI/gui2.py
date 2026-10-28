import dearpygui.dearpygui as dpg
import serial_reader as sr
import serial_writer as sw
import gui_settings as settings
import dynamic_charts as dc
import Station_Sensors as snsrs
import time
from collections import deque
import pandas as pd
import random
import sys
from pathlib import Path

sensor_path = Path(__file__).parent / "Sensor Info"
sys.path.append(str(sensor_path))

ROTATE_ENABLED = True

valid_connection = False
last_timestamp = 0
last_packet_time = time.time()
disconnect_timeout = sr.ECU_LINK_TIMEOUT_S # seconds, shared with the feedback LEDs
last_appended_timestamp = 0
fill_started = 0
fill_time = 0
fill_min = 0
fill_sec = 0
batt_rem_time = 0

# CSV for fill data
df = pd.read_csv("data10.csv")
df_fill = df.iloc[1030:1250]  # rows fill start: 1036 end: 1088
csv_time = (df_fill["Time[ms]"] / 1000).tolist()
csv_pt1  = df_fill["PT1[psi]"].tolist()
csv_pt4  = df_fill["PT4[psi]"].tolist()

csv_fill_start = 1036363 / 1000
csv_fill_end = 1087848 / 1000

class dpgVariable:
    plotBuffer = 1

MAX_POINTS = 2000  # number of points shown in plot
lastCmdTime = 0
# Get current timestamp as starting point

# rolling buffers, pre-filled with starting timestamp
timestamps = deque([sr.ecuTelem.timestamp], maxlen=MAX_POINTS)
pt1_list = deque([sr.ecuTelem.pt1], maxlen=MAX_POINTS)
pt4_list = deque([sr.ecuTelem.pt4], maxlen=MAX_POINTS)
fill_live_time = []
fill_pt1_list = []
fill_pt4_list = []

# GPS track (lon, lat) history for the Map tab -- only appended on a valid,
# new fix (see updateGpsMap()), so it doesn't fill with repeated/blank points.
gps_track_lon = deque(maxlen=MAX_POINTS)
gps_track_lat = deque(maxlen=MAX_POINTS)
_last_gps_point = None
_current_gps_map = None  # name of the map currently shown behind the track
fill_plot_started = False 

# Pressure strip chart (Tank=PT4, Bottle=PT1, Chamber=PT3). X is Pi wall-clock
# seconds since GUI start so the chart keeps scrolling with no radio connected.
PRESS_WINDOW_S    = 30            # visible time span while live
PRESS_HISTORY_PTS = 20 * 60 * 30  # ~30 min of history at 20 Hz telem
press_t0       = time.time()
press_t        = deque(maxlen=PRESS_HISTORY_PTS)
press_tank     = deque(maxlen=PRESS_HISTORY_PTS)
press_bottle   = deque(maxlen=PRESS_HISTORY_PTS)
press_chamber  = deque(maxlen=PRESS_HISTORY_PTS)
press_paused   = False
_press_dirty   = False  # new sample since the series were last pushed

# Height reserved for the tab bar at the top of the right-hand panel.
RIGHT_TAB_BAR_H = 34

# Lat/lon readout overlaid on the top-right corner of the map.
GPS_COORD_W, GPS_COORD_H = 310, 100

# Frames left before releasing the GPS map's axis lock (see frame_gps_map()).
_gps_map_limit_frames = 0

active_errors = {}  # dict of {error_id: row_tag}

# Status bar boxes: a shared height so every box lines up.
STATUS_BOX_H = settings.STATUS_BAR_SIZE[1] - 4

gui_loopTime = deque([0], maxlen=MAX_POINTS)
gui_AvgloopTimePlot = deque([0], maxlen=MAX_POINTS)

guiLoopTime = 0
frameTime = 0

fc_state = 0 # this will eventually come from the flight computer. temporary
is_dark_theme = True  # start in dark mode (DPG default)

_cpu_temp_cache     = 0.0
_cpu_temp_last_read = 0.0

def get_cpu_temp():
    """Ground-station (Raspberry Pi) CPU temp in °C. Returns 0.0 if unavailable
    (e.g. running on a non-Pi dev machine) so callers can always treat this as
    a float — never a string — for plotting/formatting. Throttled to
    settings.CPU_TEMP_POLL_INTERVAL_S since it's polled every frame."""
    global _cpu_temp_cache, _cpu_temp_last_read
    now = time.time()
    if now - _cpu_temp_last_read < settings.CPU_TEMP_POLL_INTERVAL_S:
        return _cpu_temp_cache
    _cpu_temp_last_read = now
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_raw = f.read()
        # Convert milli-degrees to Celsius and round it
        _cpu_temp_cache = round(float(temp_raw) / 1000.0, 1)
    except (FileNotFoundError, ValueError, OSError):
        _cpu_temp_cache = 0.0
    return _cpu_temp_cache
    
def toggle_theme():
    global is_dark_theme
    is_dark_theme = not is_dark_theme
    if is_dark_theme:
        dpg.bind_theme(dark_theme)
        dpg.configure_item("theme_button", label="Light")
    else:
        dpg.bind_theme(light_theme)
        dpg.configure_item("theme_button", label="Dark")
    dc.set_dark_mode(is_dark_theme)

def _config(sender, keyword, user_data):
    widget_type = dpg.get_item_type(sender)
    items = user_data

    if widget_type == "mvAppItemType::mvRadioButton":
        value = True
    else:
        keyword = dpg.get_item_label(sender)
        value = dpg.get_value(sender)

    if isinstance(user_data, list):
        for item in items:
            dpg.configure_item(item, **{keyword: value})
    else:
        dpg.configure_item(items, **{keyword: value})
        
def _log(sender, app_data, user_data):
    print(f"sender: {sender}, \t app_data: {app_data}, \t user_data: {user_data}")

def updateStatusBar():
    global fill_started, fill_time, fill_min, fill_sec

    # Connection status
    if not snsrs.ON_PI:
        conn_color = [0, 200, 255]
        conn_label = "SIMULATION"
        conn_pos = [26, draw_y // 2 - 19]
    elif valid_connection == True:
        conn_color = [0, 255, 0]
        conn_label = "CONNECTED"
        conn_pos = [31, draw_y // 2 - 19]
    else:
        conn_color = [255, 0, 0]
        conn_label = "DISCONNECTED"
        conn_pos = [6, draw_y // 2 - 17]
        
    # Safe, Arm, Fired status
    if sr.ecuTelem.armStatus_b:
        if sr.ecuTelem.pyroFireStatus_b:
            arm_color = [255, 30, 30]
            arm_label = "FIRED"
            arm_pos = [28, draw_y // 2 - 20]
        else:
            arm_color = [255, 115, 0]
            arm_label = "ARMED"
            arm_pos = [28, draw_y // 2 - 20]
    else:
        arm_color = [0, 255, 0]
        arm_label = "SAFE"
        arm_pos = [37, draw_y // 2 - 20]

    # Uptime counter
    if valid_connection == True:
        stampSecs = sr.ecuTelem.timestamp / 1000
        tov_min = (stampSecs / 60) % 60
        tov_hour = round(round(stampSecs / 60, 0) / 60, 0)
        tov_sec = stampSecs % 60
        dpg.set_value("tov", f"Uptime:{int(tov_hour):02d}:{int(tov_min):02d}:{int(tov_sec):02d}") # make this the serial timestamp
    
    # Fill time counter
    if sr.ecuTelem.fillVlvStatus_b == 1:
        if not fill_started:
            fill_time = time.time()  # (re)start timer
            fill_started = True
        # always update display while filling
        elapsed = time.time() - fill_time
        fill_min = int(elapsed / 60) % 60
        fill_sec = int(elapsed) % 60

    elif sr.ecuTelem.fillVlvStatus_b == 0:
        if fill_started:
            fill_started = False  # stop timer, freeze display (fill_min/fill_sec unchanged)
    dpg.set_value("live_fill_time", f"Fill Time:{fill_min:02}:{fill_sec:02}")
        
    # GPS Fix Status
    gps_fix = bool(sr.streamTelem.gpsFixValid_b)
    if gps_fix:
        gps_color = [0, 255, 0] 
        gps_label = "FIX" 
        gps_pos = [32, draw_y // 2 - 20]
    else:
        gps_color = [255, 0, 0]
        gps_label = "NO FIX"
        gps_pos = [4, draw_y // 2 - 20]
    
    # Radio Status      
    rssi_bars = rssi_to_bars(sr.ecuTelem.rssi)

    NUM_BARS    = 5
    BAR_W       = 11
    BAR_SPACING = 3
    BAR_MAX_H   = 45
    BASE_Y      = STATUS_BOX_H - 5

    for i in range(NUM_BARS):
        bar_h     = int(BAR_MAX_H * (i + 1) / NUM_BARS)
        bar_y_top = BASE_Y - bar_h
        bx        = i * (BAR_W + BAR_SPACING)
        color     = rssi_bar_color(rssi_bars) if i < rssi_bars else _inactive_bar_color()
        dpg.delete_item(f"rssi_ctrl_bar_{i}")
        dpg.draw_rectangle([bx, bar_y_top], [bx + BAR_W, BASE_Y],
                           color=color, fill=color, rounding=2,
                           tag=f"rssi_ctrl_bar_{i}", parent="rssi_drawlist")

    dpg.configure_item("rssi_ctrl_label", text=f"{sr.ecuTelem.rssi}dBm")
    
    # Battery Status    

    BATT_W    = 62
    BATT_H    = 40
    BATT_PAD  = 4
    BATT_Y    = (STATUS_BOX_H - BATT_H) // 2
    MAX_FILL  = BATT_W - BATT_PAD * 2

    fill_w = max(1, int(MAX_FILL * sr.streamTelem.stationInaBattSOC / 100))

    if sr.streamTelem.stationInaBattSOC > 50:   fill_color = [0, 200, 0]
    elif sr.streamTelem.stationInaBattSOC > 20: fill_color = [255, 160, 0]
    else:                                       fill_color = [220, 40, 40]

    dpg.delete_item("batt_fill")
    dpg.draw_rectangle([BATT_PAD, BATT_Y + BATT_PAD],
                       [BATT_PAD + fill_w, BATT_Y + BATT_H - BATT_PAD],
                       color=fill_color, fill=fill_color, rounding=1,
                       tag="batt_fill", parent="batt_drawlist")

    # Redraw (not just reconfigure) so it stays on top of the fill bar we
    # just re-added -- each redraw appends to the end of the drawlist.
    dpg.delete_item("batt_charge_icon")
    polyX = 34
    polyY = BATT_Y+5
    dpg.draw_polygon(
        [[polyX, polyY+2], [polyX-10, polyY+16], [polyX-4, polyY+16],
         [polyX-8, polyY+28], [polyX+4, polyY+12], [polyX-2, polyY+12], [polyX+2, polyY+2]],
        color=[255, 210, 0], fill=[255, 210, 0],
        tag="batt_charge_icon", show=bool(sr.streamTelem.stationCharging_b),
        parent="batt_drawlist",
    )
    
    dpg.set_value("station_temp_status", f"{sr.streamTelem.stationTemp_c:.1f}°C")

    dpg.set_value("batt_perc_label", f"{sr.streamTelem.stationInaBattSOC}%")
    dpg.configure_item("batt_perc_label", pos=[80, draw_y // 2 - 22])



    if sr.logging_enabled:
        dpg.configure_item("rec_button", label="Stop Rec")
    else:
        dpg.configure_item("rec_button", label="Record")
        
        
    dpg.configure_item("conn_status_rect", color=conn_color, fill=conn_color)
    dpg.configure_item("conn_status_text", text=conn_label, pos=conn_pos)

    dpg.configure_item("arm_status_rect", color=arm_color, fill=arm_color)
    dpg.configure_item("arm_status_text", text=arm_label, pos=arm_pos)
    
    dpg.configure_item("tov", pos=[0, draw_y // 2 - 22])
    
    dpg.configure_item("live_fill_time", pos=[0, draw_y // 2 - 22])
    
    dpg.configure_item("gps_signal_rect", color=gps_color, fill=gps_color)
    dpg.configure_item("gps_signal_text", text=gps_label, pos=gps_pos)          
               
def rssi_to_bars(rssi: int) -> int:
    """Convert RSSI dBm to 0-5 bars."""
    if rssi >= -60:  return 5
    if rssi >= -70:  return 4
    if rssi >= -85:  return 3
    if rssi >= -100: return 2
    if rssi >= -110: return 1
    return 0

def rssi_bar_color(bars: int):
    if bars >= 4: return [0, 220, 0]
    if bars >= 3: return [180, 220, 0]
    if bars >= 2: return [255, 160, 0]
    return [220, 40, 40]

def _inactive_bar_color():
    return [60, 60, 60] if is_dark_theme else [190, 190, 190]

def _text_color():
    return [200, 200, 200] if is_dark_theme else [30, 30, 30]

def _outline_color():
    return [180, 180, 180] if is_dark_theme else [80, 80, 80]

def _batt_bg_color():
    return [30, 30, 30] if is_dark_theme else [220, 220, 220]

def _led_style(cfg):
    """(border, fill, label, text color) for a valve LED: fill follows the
    serial feedback, border lights color_cmd while the switch commands open."""
    fill = cfg["color_on"] if cfg["state"] else cfg["color_off"]
    border = cfg["color_cmd"] if cfg["cmd"] else fill
    label = cfg["label_on"] if cfg["state"] else cfg["label_off"]
    text_color = (0, 0, 0) if cfg["state"] else (100, 100, 100)
    return border, fill, label, text_color

_status_led_themes = {}   # (fill, text color) -> button theme

def _status_led_theme(fill, text_color):
    """Button theme that makes a button look like a lit/unlit LED (same
    colour when hovered or clicked, so it doesn't look interactive)."""
    key = (tuple(fill), tuple(text_color))
    if key not in _status_led_themes:
        with dpg.theme() as theme:
            with dpg.theme_component(dpg.mvButton):
                for col in (dpg.mvThemeCol_Button, dpg.mvThemeCol_ButtonHovered, dpg.mvThemeCol_ButtonActive):
                    dpg.add_theme_color(col, fill, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Text, text_color, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6, category=dpg.mvThemeCat_Core)
        _status_led_themes[key] = theme
    return _status_led_themes[key]

def _apply_status_led(name, cfg):
    on = cfg["state"]
    fill = cfg["color_on"] if on else cfg["color_off"]
    # Dark text on any bright fill (lit, or a coloured "off" like the red
    # GOOD LEDs); grey text only on a dim unlit fill.
    text_color = (0, 0, 0) if max(fill) > 100 else (140, 140, 140)
    dpg.configure_item(f"sled_{name}", label=cfg["label_on"] if on else cfg["label_off"])
    dpg.bind_item_theme(f"sled_{name}", _status_led_theme(fill, text_color))

def update_status_leds():
    """Update the status LEDs that changed (state is set in
    sr.update_indicators())."""
    for name, cfg in settings.status_leds.items():
        on = sr.gui_leds.get(name, (0, 0))[0]
        if on != cfg["state"]:
            cfg["state"] = on
            _apply_status_led(name, cfg)

def update_leds():
    """Draw the GUI LEDs from sr.gui_leds. What they show is decided in
    sr.update_indicators() -- this only redraws the ones that changed."""
    update_status_leds()
    for name, cfg in settings.led_panel_states.items():
        state, cmd = sr.gui_leds.get(name, (0, 0))
        if state != cfg["state"] or cmd != cfg["cmd"]:
            cfg["state"], cfg["cmd"] = state, cmd
            border, fill, label, text_color = _led_style(cfg)

            dpg.configure_item(f"led_{name}",     color=border, fill=fill)
            dpg.configure_item(f"led_name_{name}",   color=text_color)
            dpg.configure_item(f"led_status_{name}", text=label, color=text_color)
      
def updateDebugWindow():
    dpg.set_value("cpu_temp",               f"Ground Station CPU Temp: {sr.streamTelem.cpuTemp_c}°C")
    dpg.set_value("station_temp",           f"Ground Station Temp: {sr.streamTelem.stationTemp_c:0.2f}°C")
    dpg.set_value("station_alt",            f"Ground Station Altitude: {sr.streamTelem.stationBaroAlt_m:0.2f} m")
    dpg.set_value("station_chrg_v",         f"Ground Station VUSB: {sr.streamTelem.stationADCChargeVolts:0.2f}V")
    dpg.set_value("station_batt_v",         f"Ground Station Battery: {sr.streamTelem.stationADCBattVolts:0.2f}V")
    dpg.set_value("station_radio_v",        f"Ground Station Radio: {sr.streamTelem.stationADCRadioVolts:0.2f}V")
    dpg.set_value("station_batt_current",   f"Ground Station Batt Current: {sr.streamTelem.stationInaBattCurrent:0.3f}A")
    dpg.set_value("station_batt_pwr",       f"Ground Station Batt Power: {sr.streamTelem.stationInaBattPower:0.3f}W")
    dpg.set_value("station_ina_volts",      f"Ground Station INA Volts: {sr.streamTelem.stationInaBattVolts:0.2f}V")
    dpg.set_value("station_ina_soc",        f"Ground Station Batt SOC: {sr.streamTelem.stationInaBattSOC:0.2f}%")

    dpg.set_value("gps_fix",                f"GPS Fix: {'VALID' if sr.streamTelem.gpsFixValid_b else 'NO FIX'}")
    dpg.set_value("gps_lat",                f"GPS Latitude: {sr.streamTelem.gpsLat:0.6f}°")
    dpg.set_value("gps_lon",                f"GPS Longitude: {sr.streamTelem.gpsLon:0.6f}°")
    dpg.set_value("gps_alt",                f"GPS Altitude: {sr.streamTelem.gpsAlt_ft:0.1f} ft")
    dpg.set_value("gps_numsv",              f"GPS Satellites: {sr.streamTelem.gpsNumSV}")
    dpg.set_value("gps_hdop",               f"GPS HDOP: {sr.streamTelem.gpsHDOP:0.2f}")
    dpg.set_value("gps_speed",              f"GPS Speed: {sr.streamTelem.gpsSpeed_kts:0.2f} kts")
    dpg.set_value("gps_course",             f"GPS Course: {sr.streamTelem.gpsCourse_deg:0.1f}°")
    dpg.set_value("gps_time",               f"GPS Time (UTC): {sr.streamTelem.gpsTime or '--'}")
    dpg.set_value("gps_date",               f"GPS Date (UTC): {sr.streamTelem.gpsDate or '--'}")
    dpg.set_value("gps_sats_visible",       f"GPS Satellites In View: {sr.streamTelem.gpsSatsVisible}")
    dpg.set_value("gps_max_cno",            f"GPS Best Signal (C/N0): {sr.streamTelem.gpsMaxCNO:0.0f} dB-Hz")

# BQ25887 lines on the Debug > Charger tab: tag -> formatter(streamTelem).
_CHGR_FAULTS = [("chgrVbusOvp_b", "VBUS OVP"), ("chgrThermalShutdown_b", "THERMAL SHUTDOWN"),
                ("chgrSafetyTimerExpired_b", "SAFETY TIMER"), ("chgrCbTopOv_b", "TOP CELL OV"),
                ("chgrCbBotOv_b", "BOT CELL OV"), ("chgrCbOverCurrent_b", "CB OVERCURRENT")]
_CHGR_LIMITS = [("chgrIindpm_b", "IINDPM"), ("chgrVindpm_b", "VINDPM"), ("chgrThermalReg_b", "TREG")]
_CHGR_EVENTS = [(n, n[len("chgrFlag"):-2]) for n in sr.streamTelem.__dataclass_fields__ if n.startswith("chgrFlag")]

def _active(t, pairs):
    return ", ".join(label for name, label in pairs if getattr(t, name)) or "none"

CHARGER_DEBUG_LINES = {
    "chgr_link":    lambda t: f"Charger: {'OK' if t.chgrConnected_b else 'NO RESPONSE'}  (PN {t.chgrPartNum} rev {t.chgrDevRev}, re-applied {t.chgrReapplyCount}x)",
    "chgr_state":   lambda t: f"State: {t.chgrChargeStatStr or '--'}",
    "chgr_input":   lambda t: f"Input: {t.chgrVbusStatStr or '--'}  PG={t.chgrPowerGood_b}",
    "chgr_vbus":    lambda t: f"VBUS: {t.chgrVbus_v:0.3f} V  {t.chgrIbus_a:0.3f} A",
    "chgr_vbat":    lambda t: f"VBAT: {t.chgrVbat_v:0.3f} V  Ichg {t.chgrIchg_a:0.3f} A",
    "chgr_cells":   lambda t: f"Cells: top {t.chgrVcellTop_v:0.3f} V  bot {t.chgrVcellBot_v:0.3f} V  (d {abs(t.chgrVcellTop_v - t.chgrVcellBot_v)*1000:0.0f} mV)",
    "chgr_balance": lambda t: f"Balancing: {'ACTIVE' if t.chgrCbActive_b else 'off'}  CV top={t.chgrCbTopCv_b} bot={t.chgrCbBotCv_b}",
    "chgr_temp":    lambda t: f"Die {t.chgrTdie_c:0.1f} C   TS {t.chgrTs_pct:0.1f}% ({t.chgrTsStatStr or '--'})",
    "chgr_ico":     lambda t: f"ICO: {t.chgrIcoStatStr or '--'}  limit {t.chgrIcoIlim_ma} mA",
    "chgr_limits":  lambda t: f"Limiting: {_active(t, _CHGR_LIMITS)}",
    "chgr_faults":  lambda t: f"Faults: {_active(t, _CHGR_FAULTS)}",
    "chgr_events":  lambda t: f"Events: {_active(t, _CHGR_EVENTS)}",
}

def updateChargerDebug():
    for tag, fmt in CHARGER_DEBUG_LINES.items():
        dpg.set_value(tag, fmt(sr.streamTelem))

# TCA9555 Debug > IO tab. Pin states come from chip.state, cached by
# snsrs.poll_io_expanders() in sensor_loop; the Set boxes write straight to
# the chip on Enter.
IOX_STATE_COLORS = {1: (0, 220, 0), 0: (150, 150, 150), None: (255, 60, 60)}
_iox_msg = {}   # chip name -> last override result, shown on its status line

def _iox_override(sender, app_data, user_data):
    chip_name, pin = user_data
    txt = app_data.strip()
    if txt not in ("0", "1"):
        _iox_msg[chip_name] = f"{pin}: enter 0 or 1, not {txt!r}"
        return
    try:
        chip = snsrs.io_expanders[chip_name]
        if settings.TCA9555_CHIPS[chip_name]["pins"][pin]["mode"] == "in":
            chip.sim_set_input(pin, int(txt))   # only offered on simulated chips
        else:
            chip.write_pin(pin, int(txt))
        _iox_msg[chip_name] = f"{pin} set to {txt}"
    except Exception as e:
        _iox_msg[chip_name] = f"{pin} write failed: {e}"
    dpg.set_value(sender, "")

def updateIoxDebug():
    for name, chip in snsrs.io_expanders.items():
        link = "OK" if chip.state is not None else "NO RESPONSE"
        dpg.set_value(f"iox_{name}_status",
                      f"{name} @0x{settings.TCA9555_CHIPS[name]['address']:02X}: {link}  "
                      f"(re-applied {chip.reapply_count}x)  {_iox_msg.get(name, '')}")
        for bit, pin in enumerate(snsrs.TCA9555.PIN_NAMES):
            val = None if chip.state is None else (chip.state >> bit) & 1
            dpg.set_value(f"iox_{name}_{pin}", "--" if val is None else str(val))
            dpg.configure_item(f"iox_{name}_{pin}", color=IOX_STATE_COLORS[val])

def updateGpsMap():
    global _last_gps_point, _current_gps_map
    if sr.streamTelem.gpsFixValid_b:
        dpg.set_value("gps_coord_lat", f"Lat: {sr.streamTelem.gpsLat:11.6f}°")
        dpg.set_value("gps_coord_lon", f"Lon: {sr.streamTelem.gpsLon:11.6f}°")
    else:
        dpg.set_value("gps_coord_lat", "Lat:      NO FIX")
        dpg.set_value("gps_coord_lon", "Lon:      NO FIX")
        return

    point = (sr.streamTelem.gpsLon, sr.streamTelem.gpsLat)
    if point == _last_gps_point:
        return  # no new fix since last frame
    _last_gps_point = point

    gps_track_lon.append(point[0])
    gps_track_lat.append(point[1])

    dpg.set_value("gps_map_trail", [list(gps_track_lon), list(gps_track_lat)])
    dpg.set_value("gps_map_current", [[point[0]], [point[1]]])

    # Switch the background image if the fix moved into a different map's
    # bounding box (or out of all of them, in which case keep showing
    # whichever map was displayed last rather than blanking it).
    lon, lat = point
    for name, m in gps_map_textures.items():
        (lon_min, lat_min), (lon_max, lat_max) = m["bounds_min"], m["bounds_max"]
        if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
            if name != _current_gps_map:
                _current_gps_map = name
                if dpg.does_item_exist("gps_map_bg"):
                    dpg.configure_item(
                        "gps_map_bg",
                        texture_tag=m["texture_tag"],
                        bounds_min=m["bounds_min"],
                        bounds_max=m["bounds_max"],
                    )
                frame_gps_map(m)
            break

def frame_gps_map(m):
    """Point the map view at m's bounds. The lock is held for a couple of
    rendered frames and then released in release_gps_map_limits() so the user
    can still pan/zoom -- releasing it in the same frame (before ImPlot ever
    sees it) cancels it and leaves the view stuck at the default 0..1 range."""
    global _gps_map_limit_frames
    (lon_min, lat_min), (lon_max, lat_max) = m["bounds_min"], m["bounds_max"]
    dpg.set_axis_limits("gps_map_xaxis", lon_min, lon_max)
    dpg.set_axis_limits("gps_map_yaxis", lat_min, lat_max)
    _gps_map_limit_frames = 2

def release_gps_map_limits():
    global _gps_map_limit_frames
    if _gps_map_limit_frames > 0:
        _gps_map_limit_frames -= 1
        if _gps_map_limit_frames == 0:
            dpg.set_axis_limits_auto("gps_map_xaxis")
            dpg.set_axis_limits_auto("gps_map_yaxis")

def toggle_press_pause():
    global press_paused, _press_dirty
    press_paused = not press_paused
    dpg.configure_item("press_pause_button", label="Resume" if press_paused else "Pause")
    dpg.configure_item("press_pause_hint", show=press_paused)
    if press_paused:
        # Hand the full history to the plot and unlock X so the user can drag
        # back through it (wheel zooms). Y keeps range-fitting to the view.
        _push_press_series(full=True)
        dpg.set_axis_limits_auto("press_x_axis")
    else:
        _press_dirty = True  # snap back to live on the next update

def _push_press_series(full=False):
    t = list(press_t)
    n = len(t)
    if not full and n:
        # Live: only send what's on screen (plus a little margin) instead of
        # the whole 30 min history every frame.
        cutoff = t[-1] - PRESS_WINDOW_S * 1.5
        start = n
        while start > 0 and t[start - 1] >= cutoff:
            start -= 1
        start = max(0, start - 1)
    else:
        start = 0
    t = t[start:]
    dpg.set_value("press_tank_series",    [t, list(press_tank)[start:]])
    dpg.set_value("press_bottle_series",  [t, list(press_bottle)[start:]])
    dpg.set_value("press_chamber_series", [t, list(press_chamber)[start:]])

def updatePressPlot(now):
    global _press_dirty
    if press_paused:
        return
    if _press_dirty:
        _push_press_series()
        _press_dirty = False
    now_s = now - press_t0
    dpg.set_axis_limits("press_x_axis", now_s - PRESS_WINDOW_S, now_s)

def updateLiveInfoWindow():
    global pt1_list, pt4_list, batt_rem_time
    dpg.set_value("rkt_tank_pressure", f"{sr.ecuTelem.pt4:.1f} psi")
    dpg.set_value("rkt_bottle_pressure", f"{sr.ecuTelem.pt1:.1f} psi")
    dpg.set_value("rkt_chamber_pressure", f"{sr.ecuTelem.pt3:.1f} psi")
    dpg.set_value("rkt_ecu_temp", f"ECU Temp: {sr.ecuTelem.boardTemp_c:.1f}°C")
    dpg.set_value("rkt_ecu_batt_volts", f"Battery Voltage: {sr.ecuTelem.battery_V:.1f}V")
    dpg.set_value("rkt_alt_ft", f"Altitude: {sr.ecuTelem.altitude_ft:.1f} ft")
    dpg.set_value("rkt_vert_vel", f"Vertical Velocity: {sr.ecuTelem.verticalVelocity_fps:.1f} ft/s")
    dpg.set_value("rkt_max_vel", f"Max Speed: {sr.ecuTelem.maxVel_fps:.1f} ft/s ({sr.ecuTelem.maxMach}M)")
    dpg.set_value("rkt_max_alt", f"Max Altitude: {sr.ecuTelem.maxAlt_ft:.1f} ft")
    dpg.set_value("rkt_max_g", f"Max Acceleration: {sr.ecuTelem.maxG:.1f}G")

def update_error_table():
    errors = {
        "sd_card": ("SD CARD ERROR", sr.streamTelem.sd_state == 0),
        "rkt_low_batt": ("LOW ECU BATTERY", sr.ecuTelem.battery_V < 7.4),
        "station_low_batt": ("LOW STATION BATTERY", sr.streamTelem.stationADCBattVolts < 7.4),
        "high_cpu_temp": (f"GROUND STATION CPU TEMP HIGH)", sr.streamTelem.cpuTemp_c >= settings.CPU_TEMP_WARN_C),
    }

    for error_id, (message, is_active) in errors.items():
        if is_active and error_id not in active_errors:
            # add new row
            with dpg.table_row(parent="error_table", tag=f"err_row_{error_id}"):
                dpg.add_text(message, color=[255, 50, 50])
                dpg.bind_item_font(dpg.last_item(), settings.medium)
            active_errors[error_id] = True
        elif not is_active and error_id in active_errors:
            # remove row
            dpg.delete_item(f"err_row_{error_id}")
            del active_errors[error_id]   
    
def get_layout():
    vp_w = dpg.get_viewport_client_width()
    vp_h = dpg.get_viewport_client_height()   
    
    statusbar_x, statusbar_y = 0, 0
    statusbar_w, statusbar_h = vp_w, settings.STATUS_BAR_SIZE[1]

    info_x, info_y = 0, statusbar_h + 10
    info_w, info_h = 570, 700

    error_x, error_y = 0, info_y + info_h
    error_w = info_w
    error_h = vp_h - info_h - statusbar_h - 10

    # Tabbed right-hand panel. Each tab's page sits just below the tab bar;
    # everything inside a page is positioned relative to that page.
    panel_x, panel_y = info_w + 5, info_y
    panel_w, panel_h = vp_w - panel_x, vp_h - panel_y
    page_w,  page_h  = panel_w, panel_h - RIGHT_TAB_BAR_H

    events_w, events_h = settings.EVENTS_WINDOW_SIZE[0], settings.EVENTS_WINDOW_SIZE[1]
    events_x, events_y = page_w - events_w, 0

    press_x, press_y = 0, 0
    press_w, press_h = events_x, events_h

    map_x, map_y = 0, events_h + 5
    map_w, map_h = page_w, page_h - map_y

    return {
        "status_bar":               {"pos": (statusbar_x,       statusbar_y),       "size": (statusbar_w,       statusbar_h)},
        "right_panel":              {"pos": (panel_x,           panel_y),           "size": (panel_w,           panel_h)},
        "overview_page":            {"pos": (0,                 RIGHT_TAB_BAR_H),   "size": (page_w,            page_h)},
        "dynamic_plots_window":     {"pos": (0,                 RIGHT_TAB_BAR_H),   "size": (page_w,            page_h)},
        "events_window":            {"pos": (events_x,          events_y),          "size": (events_w,          events_h)},
        "bus_info_window":          {"pos": (info_x,            info_y),            "size": (info_w,            info_h)},
        "press_plot_window":        {"pos": (press_x,           press_y),           "size": (press_w,           press_h)},
        "press_plot":               {"pos": (0,                 30),                "size": (press_w-16,        press_h-40)},
        "error_window":             {"pos": (error_x,           error_y),           "size": (error_w,           error_h)},
        "gps_map_window":           {"pos": (map_x,             map_y),             "size": (map_w,             map_h)},
        "gps_map_plot":             {"pos": (0,                 0),                 "size": (map_w-10,          map_h-8)},
        "gps_coord_box":            {"pos": (map_w-GPS_COORD_W-22, 36),             "size": (GPS_COORD_W,       GPS_COORD_H)},
    }

def resize_viewport():
    dpg.set_item_width("main_window", dpg.get_viewport_client_width())
    dpg.set_item_height("main_window", dpg.get_viewport_client_height())
    
    layout = get_layout()
    for tag, vals in layout.items():
        dpg.set_item_pos(tag, vals["pos"])
        dpg.set_item_width(tag, vals["size"][0])
        dpg.set_item_height(tag, vals["size"][1])
        
        
dpg.create_context()
settings.createFonts()
dpg.bind_font(settings.default)

# GPS moving-map background images (see settings.GPS_MAPS). Loaded once at
# startup; updateGpsMap() picks whichever one's bounding box contains the
# current fix and points the plot's image_series at it.
gps_map_textures = {}
with dpg.texture_registry():
    for m in settings.GPS_MAPS:
        tex_w, tex_h, _, tex_data = dpg.load_image(m["file"])
        tex_tag = dpg.add_static_texture(tex_w, tex_h, tex_data)
        gps_map_textures[m["name"]] = {
            "texture_tag": tex_tag,
            "bounds_min": m["bounds_min"],
            "bounds_max": m["bounds_max"],
        }

# ── Dark theme (DPG default colours) ──────────────────────────────────────────
with dpg.theme() as dark_theme:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_WindowBg,        (15,  15,  15,  255))
        dpg.add_theme_color(dpg.mvThemeCol_ChildBg,         (20,  20,  20,  255))
        dpg.add_theme_color(dpg.mvThemeCol_Text,            (255, 255, 255, 255))
        dpg.add_theme_color(dpg.mvThemeCol_Button,          (55,  55,  55,  255))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered,   (75,  75,  75,  255))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,    (95,  95,  95,  255))
        dpg.add_theme_color(dpg.mvThemeCol_FrameBg,         (30,  30,  30,  255))
        dpg.add_theme_color(dpg.mvThemeCol_TitleBg,         (10,  10,  10,  255))
        dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive,   (20,  20,  20,  255))
        dpg.add_theme_color(dpg.mvThemeCol_Tab,             (30,  30,  30,  255))
        dpg.add_theme_color(dpg.mvThemeCol_TabHovered,      (55,  55,  55,  255))
        dpg.add_theme_color(dpg.mvThemeCol_TabActive,       (50,  50,  50,  255))
        dpg.add_theme_color(dpg.mvThemeCol_Header,          (45,  45,  45,  255))
        dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered,   (65,  65,  65,  255))
        dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg,     (10,  10,  10,  255))
        dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab,   (60,  60,  60,  255))
        dpg.add_theme_color(dpg.mvThemeCol_Border,          (60,  60,  60,  255))
        dpg.add_theme_color(dpg.mvThemeCol_Separator,       (60,  60,  60,  255))
        dpg.add_theme_color(dpg.mvThemeCol_PopupBg,         (20,  20,  20,  255))

# ── Light theme ────────────────────────────────────────────────────────────────
with dpg.theme() as light_theme:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_WindowBg,        (235, 235, 235, 255))
        dpg.add_theme_color(dpg.mvThemeCol_ChildBg,         (220, 220, 220, 255))
        dpg.add_theme_color(dpg.mvThemeCol_Text,            (10,  10,  10,  255))
        dpg.add_theme_color(dpg.mvThemeCol_Button,          (180, 180, 180, 255))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered,   (160, 160, 160, 255))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,    (140, 140, 140, 255))
        dpg.add_theme_color(dpg.mvThemeCol_FrameBg,         (200, 200, 200, 255))
        dpg.add_theme_color(dpg.mvThemeCol_TitleBg,         (190, 190, 190, 255))
        dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive,   (170, 170, 170, 255))
        dpg.add_theme_color(dpg.mvThemeCol_Tab,             (190, 190, 190, 255))
        dpg.add_theme_color(dpg.mvThemeCol_TabHovered,      (160, 160, 160, 255))
        dpg.add_theme_color(dpg.mvThemeCol_TabActive,       (170, 170, 170, 255))
        dpg.add_theme_color(dpg.mvThemeCol_Header,          (180, 180, 180, 255))
        dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered,   (160, 160, 160, 255))
        dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg,     (210, 210, 210, 255))
        dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab,   (150, 150, 150, 255))
        dpg.add_theme_color(dpg.mvThemeCol_Border,          (160, 160, 160, 255))
        dpg.add_theme_color(dpg.mvThemeCol_Separator,       (160, 160, 160, 255))
        dpg.add_theme_color(dpg.mvThemeCol_PopupBg,         (225, 225, 225, 255))

dpg.bind_theme(dark_theme)  # apply dark theme on startup
dpg.create_viewport(title='Flight Computer Viewer', width=settings.WINDOW_DIM[0], height=settings.WINDOW_DIM[1])
layout = get_layout()

with dpg.window(tag="main_window", label="Hybrid Rocket Data Viewer", width=settings.TAB_WINDOW_DIM[0], height=settings.TAB_WINDOW_DIM[1], pos=settings.TAB_WINDOW_POS, 
                min_size=settings.WINDOW_DIM,no_title_bar=True, no_scrollbar=True, no_move=True, no_resize=True):
    
    # Tight padding for the status-bar boxes: the default child_window
    # padding was eating enough of the 60px status bar height to clip
    # content at the bottom. Binding this to the outer "status_bar"
    # container cascades it to every nested box too.
    with dpg.theme() as status_bar_theme:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 4, 1, category=dpg.mvThemeCat_Core)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 6, 2, category=dpg.mvThemeCat_Core)

    # Status Bar
    with dpg.child_window(width=layout["status_bar"]["size"][0], height=layout["status_bar"]["size"][1], pos=layout["status_bar"]["pos"], tag="status_bar", no_scrollbar=True):
        dpg.bind_item_theme("status_bar", status_bar_theme)
        with dpg.group(horizontal=True):

            _draw_t = 3.0
            draw_rounding = 6
            draw_color = [100, 100, 100]
            draw_y = STATUS_BOX_H - 4

            # ---- Connection status ----
            with dpg.child_window(width=220, height=STATUS_BOX_H, border=True, no_scrollbar=True):
                with dpg.drawlist(width=216, height=STATUS_BOX_H):
                    dpg.draw_rectangle([2, 1], [212, draw_y], rounding=draw_rounding, thickness=_draw_t, color=draw_color, fill=draw_color, tag="conn_status_rect")
                    dpg.draw_text([30, draw_y // 2 - 15], "CONNECTED", color=[0, 0, 0], size=37, tag="conn_status_text")

            # ---- Arm / Fired status ----
            with dpg.child_window(width=150, height=STATUS_BOX_H, border=True, no_scrollbar=True):
                with dpg.drawlist(width=146, height=STATUS_BOX_H):
                    dpg.draw_rectangle([2, 1], [142, draw_y], rounding=draw_rounding, thickness=_draw_t, color=draw_color, fill=draw_color, tag="arm_status_rect")
                    dpg.draw_text([38, draw_y // 2 - 15], "SAFE", color=[0, 0, 0], size=40, tag="arm_status_text")

            # ---- Uptime ----
            with dpg.child_window(width=280, height=STATUS_BOX_H, border=True, no_scrollbar=True):
                txt_tov = dpg.add_text("Uptime: 00:00:00", tag="tov")
                dpg.bind_item_font(txt_tov, settings.xl)

            dpg.add_spacer(width=10)
            
            # ---- Fill Time ----
            with dpg.child_window(width=300, height=STATUS_BOX_H, border=True, no_scrollbar=True):
                with dpg.group(horizontal=True):
                    dpg.add_text("Fill Time: 00:00", tag="live_fill_time")
                    dpg.bind_item_font(dpg.last_item(), settings.xl)

            dpg.add_spacer(width=50)

            # ---- Ground station temp ----
            with dpg.child_window(width=140, height=STATUS_BOX_H, border=True, no_scrollbar=True):
                dpg.add_text("--.-°C", tag="station_temp_status")
                dpg.bind_item_font(dpg.last_item(), settings.xl)

            # ---- GPS Signal ----
            with dpg.child_window(width=120, height=STATUS_BOX_H, border=True, no_scrollbar=True):
                with dpg.drawlist(width=120, height=STATUS_BOX_H):
                    dpg.draw_rectangle([2, 1], [116, draw_y], rounding=draw_rounding, thickness=_draw_t, color=draw_color, fill=draw_color, tag="gps_signal_rect")
                    dpg.draw_text([14, draw_y // 2 - 15], "NO FIX", color=[0, 0, 0], size=40, tag="gps_signal_text")

            # ---- Radio Signal (RSSI bars) ----
            NUM_BARS     = 5
            BAR_W        = 11
            BAR_SPACING  = 3
            BAR_MAX_H    = 28
            GROUP_W      = NUM_BARS * (BAR_W + BAR_SPACING)
            BASE_Y       = STATUS_BOX_H - 14
            DBM_SIZE     = 40
            DBM_X        = GROUP_W + 6
            TOTAL_W      = DBM_X + 140

            with dpg.child_window(width=TOTAL_W, height=STATUS_BOX_H, border=True, no_scrollbar=True):
                with dpg.drawlist(width=TOTAL_W, height=STATUS_BOX_H, tag="rssi_drawlist"):
                    dpg.draw_text([DBM_X, draw_y // 2 - 20], "0dBm", color=[200,200,200], size=DBM_SIZE, tag="rssi_ctrl_label")
                    for i in range(NUM_BARS):
                        bar_h     = int(BAR_MAX_H * (i + 1) / NUM_BARS)
                        bar_y_top = BASE_Y - bar_h
                        bx        = i * (BAR_W + BAR_SPACING)
                        dpg.draw_rectangle([bx, bar_y_top], [bx + BAR_W, BASE_Y+50],
                                           color=[60,60,60], fill=[60,60,60], rounding=2,
                                           tag=f"rssi_ctrl_bar_{i}")

            # ---- Battery % ----
            BATT_W       = 62
            BATT_H       = 40
            BATT_TIP_W   = 6
            BATT_TIP_H   = 12
            BATT_PAD     = 4
            BATT_Y       = (STATUS_BOX_H - BATT_H) // 2
            BATT_TIP_Y   = BATT_Y + (BATT_H - BATT_TIP_H) // 2
            PERC_X       = BATT_W + BATT_TIP_W + 8
            BATT_TOTAL_W = PERC_X

            with dpg.child_window(width=BATT_TOTAL_W + 80, height=STATUS_BOX_H, border=True, no_scrollbar=True):
                with dpg.group(horizontal=True):
                    with dpg.drawlist(width=BATT_TOTAL_W, height=STATUS_BOX_H, tag="batt_drawlist"):
                        # battery body outline
                        dpg.draw_rectangle([0, BATT_Y], [BATT_W, BATT_Y + BATT_H],
                                           color=[180,180,180], fill=[30,30,30], rounding=2, thickness=2,
                                           tag="batt_outline")
                        # battery tip
                        dpg.draw_rectangle([BATT_W, BATT_TIP_Y], [BATT_W + BATT_TIP_W, BATT_TIP_Y + BATT_TIP_H],
                                           color=[180,180,180], fill=[180,180,180], rounding=1,
                                           tag="batt_tip")
                        # fill bar (dynamic)
                        dpg.draw_rectangle([BATT_PAD, BATT_Y + BATT_PAD],
                                           [BATT_PAD + 1, BATT_Y + BATT_H - BATT_PAD],
                                           color=[60,60,60], fill=[60,60,60], rounding=1, tag="batt_fill")
                        # charging bolt -- shown over the icon when stationCharging_b == 1
                        dpg.draw_polygon(
                            [[30, BATT_Y+2], [20, BATT_Y+16], [26, BATT_Y+16],
                             [22, BATT_Y+28], [34, BATT_Y+12], [28, BATT_Y+12], [32, BATT_Y+2]],
                            color=[255, 210, 0], fill=[255, 210, 0],
                            tag="batt_charge_icon", show=False,
                        )

                    # percentage text
                    dpg.add_text("0%", tag="batt_perc_label")
                    dpg.bind_item_font(dpg.last_item(), settings.xl)

            # ---- Theme toggle ----
            with dpg.child_window(width=100, height=STATUS_BOX_H, border=True, no_scrollbar=True):
                dpg.add_button(label="Light", tag="theme_button", callback=toggle_theme, width=-1, height=-1)

            # ---- Record ----
            with dpg.child_window(width=100, height=STATUS_BOX_H, border=True, no_scrollbar=True):
                dpg.add_button(label="Record", tag="rec_button", callback=sr.init_log_raw, width=-1, height=-1)

    # Detailed Info
    with dpg.child_window(width=layout["bus_info_window"]["size"][0], height=layout["bus_info_window"]["size"][1], pos=layout["bus_info_window"]["pos"], tag="bus_info_window", show=True):
        with dpg.group(width=150):
            with dpg.tab_bar(label="Main Tabs"):
                with dpg.tab(label="Live Info"):
                    # Pressures
                    with dpg.group(horizontal=True):
                        dpg.add_text("Tank Pressure:")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                        dpg.add_text("--- psi", tag="rkt_tank_pressure")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                    with dpg.group(horizontal=True):
                        dpg.add_text("Bottle Pressure:")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                        dpg.add_text("--- psi", tag="rkt_bottle_pressure")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                    with dpg.group(horizontal=True):
                        dpg.add_text("Chamber Pressure:")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                        dpg.add_text("--- psi", tag="rkt_chamber_pressure")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)      
                                          
                    dpg.add_separator()
                                                       
                    with dpg.group(horizontal=True):
                        dpg.add_text("ECU Temp: 00.00 °C", tag="rkt_ecu_temp")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)

                    with dpg.group(horizontal=True):
                        dpg.add_text("Battery Voltage: 0.00 V", tag="rkt_ecu_batt_volts")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)

                    with dpg.group(horizontal=True):
                        dpg.add_text("Altitude: 0000 ft", tag="rkt_alt_ft")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                        
                    with dpg.group(horizontal=True):
                        dpg.add_text("Vertical Velocity: 000.00 ft/s", tag="rkt_vert_vel")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                
                    dpg.add_separator()   
                    
                    with dpg.group(horizontal=True):
                        dpg.add_text("Max Speed: 000 ft/sec (0.0M)", tag="rkt_max_vel")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)

                    with dpg.group(horizontal=True):
                        dpg.add_text("Max Altitude: 0000 ft", tag="rkt_max_alt")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                        
                    with dpg.group(horizontal=True):
                        dpg.add_text("Max Acceleration: 0.0 G", tag="rkt_max_g")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)

                    dpg.add_separator()

                    # Status LED grid (settings.status_leds, set in sr.update_indicators())
                    _sl_names = list(settings.status_leds)
                    _sl_cols = settings.STATUS_LED_COLS
                    with dpg.table(header_row=False, tag="status_led_table", policy=dpg.mvTable_SizingStretchSame):
                        for _ in range(_sl_cols):
                            dpg.add_table_column()
                        for _r in range(0, len(_sl_names), _sl_cols):
                            with dpg.table_row():
                                for _name in _sl_names[_r:_r + _sl_cols]:
                                    dpg.add_button(label="", tag=f"sled_{_name}", width=-1, height=settings.STATUS_LED_H)
                                    dpg.bind_item_font(dpg.last_item(), settings.status_led)
                                    _apply_status_led(_name, settings.status_leds[_name])
                    
                    
                with dpg.tab(label="Debug"):
                    # Ctrl info
                    # with dpg.group(horizontal=True):
                    #     dpg.add_text(" ", tag="ctrl_timestamp")
                    #     dpg.add_text(" ", tag="ctrl_looptime")
                    # with dpg.group(horizontal=True):
                    #     dpg.add_text(" ", tag="ctrl_sendtime")
                    #     dpg.add_text(" ", tag="ctrl_waittime")
                    # dpg.add_text(" ", tag="stationRSSI")

                    # # DAQ info
                    # with dpg.group(horizontal=True):
                    #     dpg.add_text(" ", tag="daq_timestamp")
                    #     dpg.add_text(" ", tag="daq_looptime")
                    # dpg.add_text(" ", tag="daq_RSSI")

                    # Teensy info
                    # with dpg.group(horizontal=True):
                    #     dpg.add_text(" ", tag="tsy_timestamp")
                    #     dpg.add_text(" ", tag="tsy_looptime")
                    # dpg.add_text(" ", tag="valve_states")
                    # dpg.add_text(" ", tag="pyro_states")
                    # dpg.add_text(" ", tag="arm_state")
                    # dpg.add_text(" ", tag="dbg_sensor_state")
                    # with dpg.group(horizontal=True):
                    #     dpg.add_text(" ", tag="pt1")
                    #     dpg.add_text(" ", tag="pt2")
                    #     dpg.add_text(" ", tag="pt3")
                    # with dpg.group(horizontal=True):
                    #     dpg.add_text(" ", tag="pt4")
                    # dpg.add_text(" ", tag="batt_perc")
                    # with dpg.group(horizontal=True):
                    #     dpg.add_text(" ", tag="battVolts")
                    #     dpg.add_text(" ", tag="batt_current")
                        
                    with dpg.tab_bar(label="Debug Tabs"):
                        with dpg.tab(label="Station"):
                            dpg.add_text(" ", tag="cpu_temp")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="station_temp")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="station_alt")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="station_chrg_v")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="station_batt_v")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="station_radio_v")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="station_batt_current")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="station_batt_pwr")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="station_ina_volts")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="station_ina_soc")
                            dpg.bind_item_font(dpg.last_item(), settings.large)                            

                        with dpg.tab(label="GPS"):
                            dpg.add_text(" ", tag="gps_fix")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="gps_lat")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="gps_lon")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="gps_alt")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="gps_numsv")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="gps_hdop")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="gps_speed")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="gps_course")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="gps_time")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="gps_date")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="gps_sats_visible")
                            dpg.bind_item_font(dpg.last_item(), settings.large)
                            dpg.add_text(" ", tag="gps_max_cno")
                            dpg.bind_item_font(dpg.last_item(), settings.large)

                        with dpg.tab(label="Charger"):
                            for _tag in CHARGER_DEBUG_LINES:
                                dpg.add_text(" ", tag=_tag)
                                dpg.bind_item_font(dpg.last_item(), settings.medium)

                        with dpg.tab(label="IO"):
                            if not snsrs.io_expanders:
                                dpg.add_text("No TCA9555 chips enabled in settings")
                            with dpg.tab_bar():
                                for _name in snsrs.io_expanders:
                                    with dpg.tab(label=_name):
                                        dpg.add_text(" ", tag=f"iox_{_name}_status", wrap=layout["bus_info_window"]["size"][0] - 30)
                                        with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True,
                                                       borders_innerV=True, borders_outerV=True):
                                            dpg.add_table_column(label="Pin",   width_fixed=True, init_width_or_weight=45)
                                            dpg.add_table_column(label="Name")
                                            dpg.add_table_column(label="Mode",  width_fixed=True, init_width_or_weight=75)
                                            dpg.add_table_column(label="State", width_fixed=True, init_width_or_weight=55)
                                            dpg.add_table_column(label="Set",   width_fixed=True, init_width_or_weight=60)
                                            for _pin in snsrs.TCA9555.PIN_NAMES:
                                                _p = settings.TCA9555_CHIPS[_name]["pins"][_pin]
                                                with dpg.table_row():
                                                    dpg.add_text(_pin)
                                                    dpg.add_text(_p["name"] or "-")
                                                    dpg.add_text("in (inv)" if _p["mode"] == "in" and _p["invert"] else _p["mode"])
                                                    dpg.add_text("--", tag=f"iox_{_name}_{_pin}")
                                                    # Inputs can be set too on a simulated chip (PC testing) to fake a switch.
                                                    if _p["mode"] == "out" or getattr(snsrs.io_expanders[_name], "simulated", False):
                                                        dpg.add_input_text(width=-1, hint="0/1", on_enter=True, no_spaces=True,
                                                                           callback=_iox_override, user_data=(_name, _pin))
                                                    else:
                                                        dpg.add_text("-")


    # ERROR window
    with dpg.child_window(width=layout["error_window"]["size"][0], height=layout["error_window"]["size"][1], pos=layout["error_window"]["pos"], tag="error_window", show=True):
        dpg.add_text("Error Info")
        with dpg.table(tag="error_table", header_row=False, borders_innerH=True,
               borders_outerH=True, borders_outerV=True):
            dpg.add_table_column()
        
            
    with dpg.theme() as line_theme:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, 2, category=dpg.mvThemeCat_Plots)

    
                
    # Current-position marker: big red dot with a white outline so it stands
    # out against the satellite image.
    with dpg.theme() as gps_marker_theme:
        with dpg.theme_component(dpg.mvScatterSeries):
            dpg.add_theme_style(dpg.mvPlotStyleVar_Marker, dpg.mvPlotMarker_Circle, category=dpg.mvThemeCat_Plots)
            dpg.add_theme_style(dpg.mvPlotStyleVar_MarkerSize, 11, category=dpg.mvThemeCat_Plots)
            dpg.add_theme_style(dpg.mvPlotStyleVar_MarkerWeight, 3, category=dpg.mvThemeCat_Plots)
            dpg.add_theme_color(dpg.mvPlotCol_MarkerFill, (255, 30, 30, 255), category=dpg.mvThemeCat_Plots)
            dpg.add_theme_color(dpg.mvPlotCol_MarkerOutline, (255, 255, 255, 255), category=dpg.mvThemeCat_Plots)
            dpg.add_theme_color(dpg.mvPlotCol_Line, (255, 255, 255, 255), category=dpg.mvThemeCat_Plots)

    with dpg.theme() as gps_trail_theme:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, 3, category=dpg.mvThemeCat_Plots)
            dpg.add_theme_color(dpg.mvPlotCol_Line, (255, 220, 0, 255), category=dpg.mvThemeCat_Plots)

    # Semi-transparent dark box so the readout is legible over the map.
    with dpg.theme() as gps_coord_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (0, 0, 0, 170))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 8, 4)

    # Right-hand tabbed panel: Overview (pressures, valves, map) / Dynamic Plots
    with dpg.child_window(width=layout["right_panel"]["size"][0], height=layout["right_panel"]["size"][1], pos=layout["right_panel"]["pos"], tag="right_panel", border=False, no_scrollbar=True, no_scroll_with_mouse=True):
        # Without a group width the first tab header stretches across the whole bar.
        with dpg.group(width=150):
            with dpg.tab_bar(tag="right_tabs"):
                with dpg.tab(label="Overview"):
                    with dpg.child_window(width=layout["overview_page"]["size"][0], height=layout["overview_page"]["size"][1], pos=layout["overview_page"]["pos"], tag="overview_page", border=False, no_scrollbar=True, no_scroll_with_mouse=True):

                        # Pressure plot window
                        with dpg.child_window(width=layout["press_plot_window"]["size"][0], height=layout["press_plot_window"]["size"][1], pos=layout["press_plot_window"]["pos"], tag="press_plot_window", no_scrollbar=True):
                            with dpg.group(horizontal=True):
                                dpg.add_button(label="Pause", tag="press_pause_button", callback=toggle_press_pause, width=100)
                                dpg.add_text("Paused: drag to scroll back in time, wheel to zoom", tag="press_pause_hint", show=False)
                            with dpg.plot(label="Pressures", width=layout["press_plot"]["size"][0], height=layout["press_plot"]["size"][1], pos=layout["press_plot"]["pos"], tag="press_plot"):
                                dpg.add_plot_legend(location=dpg.mvPlot_Location_NorthWest)
                                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="press_x_axis")
                                # auto_fit + range_fit: Y fits only the data inside the visible X
                                # range, so it tracks the live window and whatever is scrolled to.
                                with dpg.plot_axis(dpg.mvYAxis, label="Pressure (psi)", tag="press_y_axis", auto_fit=True, range_fit=True):
                                    dpg.add_line_series([], [], label="Tank",    tag="press_tank_series")
                                    dpg.add_line_series([], [], label="Bottle",  tag="press_bottle_series")
                                    dpg.add_line_series([], [], label="Chamber", tag="press_chamber_series")
                            for _tag in ("press_tank_series", "press_bottle_series", "press_chamber_series"):
                                dpg.bind_item_theme(_tag, line_theme)

                        # GPS moving map window
                        with dpg.child_window(width=layout["gps_map_window"]["size"][0], height=layout["gps_map_window"]["size"][1], pos=layout["gps_map_window"]["pos"], tag="gps_map_window", show=True):

                            with dpg.plot(label="GPS Track", width=layout["gps_map_plot"]["size"][0], height=layout["gps_map_plot"]["size"][1], pos=[0,0], tag="gps_map_plot", equal_aspects=True):
                                dpg.add_plot_legend(outside=False, location=dpg.mvPlot_Location_NorthWest)
                                with dpg.plot_axis(dpg.mvXAxis, label="Longitude", tag="gps_map_xaxis"):
                                    pass
                                with dpg.plot_axis(dpg.mvYAxis, label="Latitude", tag="gps_map_yaxis"):
                                    _default_map_name = next(iter(gps_map_textures), None)
                                    if _default_map_name:
                                        _default_map = gps_map_textures[_default_map_name]
                                        dpg.add_image_series(
                                            _default_map["texture_tag"],
                                            bounds_min=_default_map["bounds_min"],
                                            bounds_max=_default_map["bounds_max"],
                                            tag="gps_map_bg",
                                        )
                                        _current_gps_map = _default_map_name
                                    # Track/marker added after the background so they draw on top of it.
                                    dpg.add_line_series([], [], label="Track", tag="gps_map_trail")
                                    dpg.add_scatter_series([], [], label="Current", tag="gps_map_current")
                            dpg.bind_item_theme("gps_map_trail", gps_trail_theme)
                            dpg.bind_item_theme("gps_map_current", gps_marker_theme)

                            # Coordinate readout, drawn after the plot so it sits on top of it.
                            with dpg.child_window(width=GPS_COORD_W, height=GPS_COORD_H, pos=layout["gps_coord_box"]["pos"], tag="gps_coord_box", border=False, no_scrollbar=True):
                                dpg.add_text("Lat:      NO FIX", tag="gps_coord_lat")
                                dpg.bind_item_font(dpg.last_item(), settings.xl)
                                dpg.add_text("Lon:      NO FIX", tag="gps_coord_lon")
                                dpg.bind_item_font(dpg.last_item(), settings.xl)
                            dpg.bind_item_theme("gps_coord_box", gps_coord_theme)

                            if _default_map_name:
                                frame_gps_map(_default_map)

                        # Events window
                        with dpg.child_window(width=layout["events_window"]["size"][0], height=layout["events_window"]["size"][1], pos=layout["events_window"]["pos"], tag="events_window", no_scrollbar=True):
                            dpg.bind_item_font(dpg.last_item(), settings.xl)

                            with dpg.drawlist(width=settings.EVENTS_WINDOW_SIZE[0]-20, height=settings.EVENTS_WINDOW_SIZE[1]-20, tag="led_drawlist"):
                                for i, (name, cfg) in enumerate(settings.led_panel_states.items()):
                                    col = i % settings.LED_COLS
                                    row = i // settings.LED_COLS
                                    x = settings.LED_SPACING_X + col * (settings.LED_W + settings.LED_SPACING_X)
                                    y = settings.LED_SPACING_Y + row * (settings.LED_H + settings.LED_SPACING_Y)

                                    border, fill, label, text_color = _led_style(cfg)

                                    # LED rectangle
                                    dpg.draw_rectangle(
                                        [x, y], [x + settings.LED_W, y + settings.LED_H],
                                        rounding=6,
                                        color=border,
                                        fill=fill,
                                        thickness=settings.LED_BORDER_THICKNESS,
                                        tag=f"led_{name}"
                                    )
                                    # name label (top-left inside)
                                    dpg.draw_text(
                                        [x + 5, y + 3],
                                        name,
                                        color=text_color,
                                        size=50,
                                        tag=f"led_name_{name}"
                                    )
                                    # status text (bottom-right inside)
                                    dpg.draw_text(
                                        [x + 5, y + settings.LED_H-50],
                                        label,
                                        color=text_color,
                                        size=38,
                                        tag=f"led_status_{name}"
                                    )

                with dpg.tab(label="Dynamic Plots"):
                    with dpg.child_window(width=layout["dynamic_plots_window"]["size"][0], height=layout["dynamic_plots_window"]["size"][1], pos=layout["dynamic_plots_window"]["pos"], tag="dynamic_plots_window", border=False):
                        dc.build_panel("dynamic_plots_window", sr.streamTelem)


def on_key_released(sender, key):
    global lastCmdTime 
    now = time.time()
    
    if now - lastCmdTime >= 0.1:
        #print(now - lastCmdTime, now , lastCmdTime)
        lastCmdTime = now
        if key == dpg.mvKey_P:
            sw.send_ping()

    if key == dpg.mvKey_Escape:
        dpg.stop_dearpygui()

with dpg.item_handler_registry(tag="vp_handler"):
    dpg.add_item_resize_handler(callback=resize_viewport)
    
dpg.set_viewport_resize_callback(resize_viewport) 

# Setup viewport

dpg.setup_dearpygui()
dpg.show_viewport()
# Fullscreen only on the ground-station Pi; on a dev PC stay windowed.
if snsrs.ON_PI:
    # Let the window manager actually map the window before requesting
    # fullscreen -- toggling immediately after show_viewport() races with
    # the WM on Linux (X11/Wayland) and the request is sometimes dropped.
    for _ in range(5):
        dpg.render_dearpygui_frame()
    dpg.toggle_viewport_fullscreen()

# Auto screen size adjust
dpg.bind_item_handler_registry("main_window", "vp_handler")
#dpg.start_dearpygui()

# ---------------- main loop ----------------
lastTime = 0

try:
    with dpg.handler_registry():
            dpg.add_key_press_handler(callback=on_key_released)
            
    while dpg.is_dearpygui_running():
        # A new ECU packet changes its timestamp; no new packet for
        # disconnect_timeout seconds = link lost.
        if sr.ecuTelem.timestamp != last_timestamp:
            last_timestamp = sr.ecuTelem.timestamp
            last_packet_time = time.time()
            valid_connection = True
        elif time.time() - last_packet_time > disconnect_timeout:
            valid_connection = False
        
        frameTime = time.time()
        # Append latest data
        if sr.ecuTelem.timestamp != last_appended_timestamp:
            last_appended_timestamp = sr.ecuTelem.timestamp
            timestamps.append(sr.ecuTelem.timestamp/1000)
            pt1_list.append(sr.ecuTelem.pt1)
            pt4_list.append(sr.ecuTelem.pt4)
            press_t.append(frameTime - press_t0)
            press_tank.append(sr.ecuTelem.pt4)
            press_bottle.append(sr.ecuTelem.pt1)
            press_chamber.append(sr.ecuTelem.pt3)
            _press_dirty = True
                
        
            
        
        #dpg.set_value("pt1_list", [list(timestamps), list(pt1_list)])
        #dpg.set_value("pt4_list", [list(timestamps), list(pt4_list)])
        #all_pressures = list(pt1_list) + list(pt4_list)
        #dpg.set_axis_limits("y_axis_pressure", min(all_pressures), max(all_pressures))


            #dpg.set_axis_limits("x_axis_busIMUaccel", start, latest)
            
        sr.streamTelem.cpuTemp_c = get_cpu_temp()

        updateLiveInfoWindow()
        updateDebugWindow()
        updateChargerDebug()
        updateIoxDebug()
        updateGpsMap()
        release_gps_map_limits()
        updatePressPlot(frameTime)
        updateStatusBar()
        update_leds()
        update_error_table()
        # Wall-clock time drives the strip charts so they keep scrolling in
        # real time even with no radio connected (telem timestamp would
        # otherwise freeze).
        dc.update(sr.streamTelem, frameTime)

        # Render one frame
        dpg.render_dearpygui_frame()
        #time.sleep(1/1000)  # 50 FPS
        
        
        guiLoopTime = (time.time() - frameTime) * 1000000

finally:
    dpg.destroy_context()
    sr.close_log()