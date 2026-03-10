import dearpygui.dearpygui as dpg
import serial_reader as sr
import serial_writer as sw
import gui_settings as settings
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
disconnect_counter = 0
disconnect_timeout = 1000 # loops 
abort_counter = 0
abort_counter_started = 0
fill_started = 0
fill_time = 0
fill_min = 0
fill_sec = 0

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
timestamps = deque([sr.streamTelem.tsy_timestamp], maxlen=MAX_POINTS)
pt1_list = deque([sr.streamTelem.pt1], maxlen=MAX_POINTS)
pt4_list = deque([sr.streamTelem.pt4], maxlen=MAX_POINTS)
fill_live_time = []
fill_pt1_list = []
fill_pt4_list = []
fill_plot_started = False 

active_errors = {}  # dict of {error_id: row_tag}

gui_loopTime = deque([0], maxlen=MAX_POINTS)
gui_AvgloopTimePlot = deque([0], maxlen=MAX_POINTS)

guiLoopTime = 0
frameTime = 0

fc_state = 0 # this will eventually come from the flight computer. temporary

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
    global abort_counter_started
    global abort_counter
    if valid_connection == True:
        dpg.configure_item("state_modal", show=False)
        abort_counter_started = 0
        conn_color = [0, 255, 0]
        conn_label = "CONNECTED"
        conn_pos = [35, draw_y // 2 - 15]
    else: 
        if sr.streamTelem.tsy_timestamp > 0 and not abort_counter_started:
            abort_counter = time.time()
            abort_counter_started = 1
            
            
            
        conn_color = [255, 0, 0]
        conn_label = "DISCONNECTED"
        conn_pos = [15, draw_y // 2 - 15]
        
    if sr.streamTelem.arm_state == True:
        arm_color = [255, 115, 0]
        arm_label = "ARMED"
        arm_pos = [35+190, draw_y // 2 - 15]
    else: 
        arm_color = [0, 255, 0]
        arm_label = "SAFE"
        arm_pos = [40+190, draw_y // 2 - 15]
        
    dpg.configure_item("conn_status_rect", color=conn_color, fill=conn_color)
    dpg.configure_item("conn_status_text", text=conn_label, pos=conn_pos)
    
    dpg.configure_item("arm_status_rect", color=arm_color, fill=arm_color)
    dpg.configure_item("arm_status_text", text=arm_label, pos=arm_pos)
    
    if valid_connection == True:
        stampSecs = sr.streamTelem.tsy_timestamp / 1000
        tov_min = (stampSecs / 60) % 60
        tov_hour = round(round(stampSecs / 60, 0) / 60, 0)
        tov_sec = stampSecs % 60
        dpg.set_value("tov", f"{int(tov_hour):02d}:{int(tov_min):02d}:{int(tov_sec):02d}") # make this the serial timestamp
        
    # show pop up if abort countdown started
    if valid_connection == False and sr.streamTelem.tsy_timestamp > 0:
        show_modal(f"ABORT")
            
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
               
def update_leds():
    new_states = {
        "FILL": sr.streamTelem.fill_state,
        "VENT": sr.streamTelem.vent_state,
        "MOV":  sr.streamTelem.mov_state,
        "ARM":  sr.streamTelem.arm_state,
        "PY1":  sr.streamTelem.py1_state,
        "PY2":  sr.streamTelem.py2_state,
        "C1":   sr.streamTelem.c1_state,
        "C2":   sr.streamTelem.c2_state,
    }
    for name, state in new_states.items():
        if state != settings.led_panel_states[name]["state"]:
            settings.led_panel_states[name]["state"] = state
            cfg = settings.led_panel_states[name]
            color = cfg["color_on"] if state else cfg["color_off"]
            label = cfg["label_on"] if state else cfg["label_off"]
            text_color = (0, 0, 0) if state else (100, 100, 100)

            dpg.configure_item(f"led_{name}",     color=color, fill=color)
            dpg.configure_item(f"led_name_{name}",   color=text_color)
            dpg.configure_item(f"led_status_{name}", text=label, color=text_color)
      
def show_modal(message: str):
    secs = int(time.time()-abort_counter)
    stampSecs = 60 - secs
    tov_min = (stampSecs / 60) % 60
    tov_hour = round(round(stampSecs / 60, 0) / 60, 0)
    tov_sec = stampSecs % 60
    dpg.set_value("abort_tov", f"ABORT IN {int(tov_min):02d}:{int(tov_sec):02d}") # make this the serial timestamp
    dpg.configure_item("state_modal", show=True)
    
def updateDebugWindow():
    dpg.set_value("ctrl_timestamp",         f"Ctrl timestamp: {sr.streamTelem.ctrl_timestamp} ms")
    dpg.set_value("ctrl_RSSI",              f"Ctrl RSSI: {sr.streamTelem.ctrl_RSSI} dBm")
    dpg.set_value("ctrl_looptime",          f"Ctrl looptime: {sr.streamTelem.ctrl_looptime} us")
    dpg.set_value("ctrl_sendtime",          f"Ctrl sendtime: {sr.streamTelem.ctrl_sendtime} us")
    dpg.set_value("ctrl_waittime",          f"Ctrl waittime: {sr.streamTelem.ctrl_waittime} us")
    dpg.set_value("daq_timestamp",          f"DAQ timestamp: {sr.streamTelem.daq_timestamp} ms")
    dpg.set_value("daq_RSSI",               f"DAQ RSSI: {sr.streamTelem.daq_RSSI} dBm")
    dpg.set_value("daq_looptime",           f"DAQ looptime: {sr.streamTelem.daq_looptime} us")
    dpg.set_value("tsy_timestamp",          f"Teensy timestamp: {sr.streamTelem.tsy_timestamp} ms")
    dpg.set_value("tsy_looptime",           f"Teensy looptime: {sr.streamTelem.tsy_looptime} us")
    dpg.set_value("valve_states",           f"Valve states: {sr.streamTelem.valve_states:08b}")
    dpg.set_value("pyro_states",            f"Pyro states: {sr.streamTelem.pyro_states:08b}")
    dpg.set_value("arm_state",              f"Arm state: {sr.streamTelem.arm_state}")
    dpg.set_value("dbg_sensor_state",       f"Sensor state: {sr.streamTelem.sensor_states:08b}")
    dpg.set_value("pt1",                    f"PT1: {round(sr.streamTelem.pt1, 2)} PSI")
    dpg.set_value("pt2",                    f"PT2: {round(sr.streamTelem.pt2, 2)} PSI")
    dpg.set_value("pt3",                    f"PT3: {round(sr.streamTelem.pt3, 2)} PSI")
    dpg.set_value("pt4",                    f"PT4: {round(sr.streamTelem.pt4, 2)} PSI")
    dpg.set_value("pt5",                    f"PT5: {round(sr.streamTelem.pt5, 2)} PSI")
    dpg.set_value("pt6",                    f"PT6: {round(sr.streamTelem.pt6, 2)} PSI")
    dpg.set_value("loadCell",               f"Load cell: {round(sr.streamTelem.loadCell, 3)} lbf")
    dpg.set_value("battVolts",              f"Battery voltage: {round(sr.streamTelem.battVolts, 3)} V")
    dpg.set_value("fiveVolts",              f"5V bus voltage: {round(sr.streamTelem.fiveVolts, 3)} V")
    dpg.set_value("radioVolts",             f"Radio voltage: {round(sr.streamTelem.radioVolts, 3)} V")
    dpg.set_value("batt_perc",              f"Battery: {lipo_2s_percent(sr.streamTelem.battVolts)}%  ({round(sr.streamTelem.battVolts, 2)}V)")
    
def updateLiveInfoWindow():
    global fill_started, fill_time, live_time, pt1_list, pt4_list, fill_min, fill_sec
    dpg.set_value("live_tank_pressure", f"{sr.streamTelem.pt4:.1f} psi")
    dpg.set_value("live_bottle_pressure", f"{sr.streamTelem.pt1:.1f} psi")
    
    if sr.streamTelem.fill_state == 1:
        if not fill_started:
            fill_time = time.time()  # (re)start timer
            fill_started = True
        # always update display while filling
        elapsed = time.time() - fill_time
        fill_min = int(elapsed / 60) % 60
        fill_sec = int(elapsed) % 60

    elif sr.streamTelem.fill_state == 0:
        if fill_started:
            fill_started = False  # stop timer, freeze display (fill_min/fill_sec unchanged)

    
    dpg.set_value("live_fill_time", f"{fill_min:02}:{fill_sec:02}")
    dpg.set_value("live_batt_perc", f"{lipo_2s_percent(sr.streamTelem.battVolts):.1f} %")
    
def updateFillPlot(): 
    global fill_plot_started, fill_time, fill_live_time, fill_pt1_list, fill_pt4_list
    
    if sr.streamTelem.fill_state == 1:
        if not fill_plot_started:
            fill_time = time.time()
            fill_plot_started = True
            fill_live_time.clear()
            fill_pt1_list.clear()
            fill_pt4_list.clear()
            dpg.set_value("pt1_curve", [[], []])
            dpg.set_value("pt4_curve", [[], []])

    
        elapsed = (time.time() - fill_time) + csv_fill_start
        fill_live_time.append(float(elapsed))
        fill_pt1_list.append(float(sr.streamTelem.pt1))
        fill_pt4_list.append(float(sr.streamTelem.pt4))

        dpg.set_value("pt1_curve", [list(fill_live_time), list(fill_pt1_list)])
        dpg.set_value("pt4_curve", [list(fill_live_time), list(fill_pt4_list)])
        
    elif sr.streamTelem.fill_state == 0:
        fill_plot_started = False  # allow re-clear on next fill
    
def update_error_table():
    errors = {
        "sd_card": ("SD CARD ERROR", sr.streamTelem.sd_state == 0),
        "low_batt": ("LOW BATTERY", sr.streamTelem.battVolts < 7.4),
    }

    for error_id, (message, is_active) in errors.items():
        if is_active and error_id not in active_errors:
            # add new row
            with dpg.table_row(parent="error_table", tag=f"err_row_{error_id}"):
                dpg.add_text(message, color=[255, 50, 50])
            active_errors[error_id] = True
        elif not is_active and error_id in active_errors:
            # remove row
            dpg.delete_item(f"err_row_{error_id}")
            del active_errors[error_id]   
    
dpg.create_context()
settings.createFonts()
dpg.bind_font(settings.default)

with dpg.window(label="Flight Computer Viewer", width=settings.TAB_WINDOW_DIM[0], height=settings.TAB_WINDOW_DIM[1], pos=settings.TAB_WINDOW_POS, 
                min_size=settings.WINDOW_DIM, max_size=settings.WINDOW_DIM,no_title_bar=True, no_move=True):
    
    # Status Bar
    with dpg.child_window(width=settings.STATUS_BAR_SIZE[0], height=settings.STATUS_BAR_SIZE[1], no_scrollbar=True):
        with dpg.group(horizontal=True):
            
            _draw_t = 3.0
            draw_size = 20
            draw_spacing = 10
            draw_rounding = draw_size/5.0
            draw_color = [100, 100, 100]
            draw_y = settings.STATUS_BAR_SIZE[1] - 15
            
            box1_x = 10
            box1_w = 180
            box2_x = box1_x + box1_w + draw_spacing
            box2_w = 115

            with dpg.drawlist(width=box2_x + box2_w + 10, height=settings.STATUS_BAR_SIZE[1]):
                
                # Connection status box
                dpg.draw_rectangle([box1_x, 1], [box1_x + box1_w, draw_y], rounding=draw_rounding, thickness=_draw_t, color=draw_color, fill=draw_color, tag="conn_status_rect")
                dpg.draw_text([box1_x + 15, draw_y // 2 - 15], "CONNECTED", color=[0, 0, 0], size=30, tag="conn_status_text")

                # Arm status box
                dpg.draw_rectangle([box2_x, 1], [box2_x + box2_w, draw_y], rounding=draw_rounding, thickness=_draw_t, color=draw_color, fill=draw_color, tag="arm_status_rect")
                dpg.draw_text([box2_x + 15, draw_y // 2 - 15], "SAFE", color=[0, 0, 0], size=30, tag="arm_status_text")

            # TOV
            txt_tov = dpg.add_text(" ", tag="tov")
            dpg.bind_item_font(txt_tov,settings.xl)
            
    with dpg.child_window(width=settings.INFO_WINDOW_SIZE[0], height=settings.INFO_WINDOW_SIZE[1], pos=settings.INFO_WINDOW_POS, tag="right_window_bus_info", show=True):
        with dpg.group(width=150):
            with dpg.tab_bar(label="Main Tabs"):
                with dpg.tab(label="Live Info"):
                    # Pressures
                    with dpg.group(horizontal=True):
                        dpg.add_text("Tank Pressure:", color=[180, 180, 180])
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                        dpg.add_text("--- psi", tag="live_tank_pressure")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                    with dpg.group(horizontal=True):
                        dpg.add_text("Bottle Pressure:", color=[180, 180, 180])
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                        dpg.add_text("--- psi", tag="live_bottle_pressure")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                        
                    dpg.add_separator()
                    
                    # Fill time
                    with dpg.group(horizontal=True):
                        dpg.add_text("Fill Time:", color=[180, 180, 180])
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                        dpg.add_text("--:--", tag="live_fill_time")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                    
                    dpg.add_separator()
                    
                    # Battery
                    with dpg.group(horizontal=True):
                        dpg.add_text("Battery:", color=[180, 180, 180])
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                        dpg.add_text("-- %", tag="live_batt_perc")
                        dpg.bind_item_font(dpg.last_item(), settings.xl)
                        
                    dpg.add_text(" ", color=[255, 0, 0], tag="sd_state")  
                    dpg.bind_item_font(dpg.last_item(), settings.xl)  
                    
                with dpg.tab(label="Debug"):
                    # Ctrl info
                    with dpg.group(horizontal=True):
                        dpg.add_text(" ", tag="ctrl_timestamp")
                        dpg.add_text(" ", tag="ctrl_looptime")
                    with dpg.group(horizontal=True):
                        dpg.add_text(" ", tag="ctrl_sendtime")
                        dpg.add_text(" ", tag="ctrl_waittime")
                    dpg.add_text(" ", tag="ctrl_RSSI")

                    # DAQ info
                    with dpg.group(horizontal=True):
                        dpg.add_text(" ", tag="daq_timestamp")
                        dpg.add_text(" ", tag="daq_looptime")
                    dpg.add_text(" ", tag="daq_RSSI")

                    # Teensy info
                    with dpg.group(horizontal=True):
                        dpg.add_text(" ", tag="tsy_timestamp")
                        dpg.add_text(" ", tag="tsy_looptime")
                    dpg.add_text(" ", tag="valve_states")
                    dpg.add_text(" ", tag="pyro_states")
                    dpg.add_text(" ", tag="arm_state")
                    dpg.add_text(" ", tag="dbg_sensor_state")
                    with dpg.group(horizontal=True):
                        dpg.add_text(" ", tag="pt1")
                        dpg.add_text(" ", tag="pt2")
                        dpg.add_text(" ", tag="pt3")
                    with dpg.group(horizontal=True):
                        dpg.add_text(" ", tag="pt4")
                        dpg.add_text(" ", tag="pt5")
                        dpg.add_text(" ", tag="pt6")
                    dpg.add_text(" ", tag="loadCell")
                    with dpg.group(horizontal=True):
                        dpg.add_text(" ", tag="battVolts")
                        dpg.add_text(" ", tag="batt_perc")
                    with dpg.group(horizontal=True):
                        dpg.add_text(" ", tag="fiveVolts")
                        dpg.add_text(" ", tag="radioVolts")
    
    # ERROR window
    with dpg.child_window(width=settings.ERROR_WINDOW_SIZE[0], height=settings.ERROR_WINDOW_SIZE[1], pos=settings.ERROR_WINDOW_POS, tag="error_window", show=True):
        dpg.add_text("Error Info")
        with dpg.table(tag="error_table", header_row=False, borders_innerH=True, 
               borders_outerH=True, borders_outerV=True):
            dpg.add_table_column()
        
            
    with dpg.theme() as line_theme:
        with dpg.theme_component(dpg.mvLineSeries):
            dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, 2, category=dpg.mvThemeCat_Plots)

    
                
    # Past pressure plot
    with dpg.child_window(width=settings.PRESS_PLOT_WINDOW_SIZE[0], height=settings.PRESS_PLOT_WINDOW_SIZE[1], pos=settings.PRESS_PLOT_WINDOW_POS, tag="press_plot_window", show=True):
                       
        with dpg.plot(label="Fill Curve", width=settings.PRESS_PLOT_WINDOW_SIZE[0]-16, height=settings.PRESS_PLOT_WINDOW_SIZE[1]-10, pos=[0,0]):
            dpg.add_plot_legend(location=dpg.mvPlot_Location_NorthEast)
            dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis_press_curve")
            dpg.set_axis_limits("x_axis_press_curve", csv_time[0], csv_time[-1])
            with dpg.plot_axis(dpg.mvYAxis, label="PSI", tag="y_axis_pressure_curve"):
                # Static CSV reference lines
                dpg.add_line_series(csv_time, csv_pt1, label="Bottle Ref", tag="csv_pt1_series")
                dpg.add_line_series(csv_time, csv_pt4, label="Tank Ref", tag="csv_pt4_series")
        
                # Live data on top
                dpg.add_line_series([], [], label="Tank Pressure", tag="pt4_curve")
                dpg.add_line_series([], [], label="Bottle Pressure", tag="pt1_curve")
                
                
                
            dpg.set_axis_limits("y_axis_pressure_curve", 0, 1100)    
    dpg.bind_item_theme("pt1_curve", line_theme)
    dpg.bind_item_theme("pt4_curve", line_theme)
                
    with dpg.child_window(width=settings.PLOT_WINDOW_SIZE[0], height=settings.PLOT_WINDOW_SIZE[1], pos=settings.PLOT_WINDOW_POS, tag="plot_window", show=True):
                       
        with dpg.plot(label="Live Pressures", width=settings.PLOT_WINDOW_SIZE[0]-16, height=400, pos=[0,0]):
            dpg.add_plot_legend()
            with dpg.plot_axis(dpg.mvXAxis, label="Timestamp", tag="x_axis_busIMUaccel"):
                pass
            with dpg.plot_axis(dpg.mvYAxis, label="PSI", tag="y_axis_pressure"):
                dpg.set_axis_limits(dpg.last_item(), -20, 20) 
                dpg.add_line_series([], [], label="Tank Pressure", tag="pt4_list")
                dpg.add_line_series([], [], label="Bottle Pressure", tag="pt1_list")
                
        
                
                
    # Events window
    with dpg.child_window(width=settings.EVENTS_WINDOW_SIZE[0], height=settings.EVENTS_WINDOW_SIZE[1], pos=settings.EVENTS_WINDOW_POS):
        dpg.bind_item_font(dpg.last_item(), settings.large)

        with dpg.drawlist(width=settings.EVENTS_WINDOW_SIZE[0]-20, height=settings.EVENTS_WINDOW_SIZE[1]-60, tag="led_drawlist"):
            for i, (name, cfg) in enumerate(settings.led_panel_states.items()):
                col = i % settings.LED_COLS
                row = i // settings.LED_COLS
                x = settings.LED_SPACING_X + col * (settings.LED_W + settings.LED_SPACING_X)
                y = settings.LED_SPACING_Y + row * (settings.LED_H + settings.LED_SPACING_Y)

                color = cfg["color_on"] if cfg["state"] else cfg["color_off"]
                label = cfg["label_on"] if cfg["state"] else cfg["label_off"]
                text_color = (0, 0, 0) if cfg["state"] else (100, 100, 100)

                # LED rectangle
                dpg.draw_rectangle(
                    [x, y], [x + settings.LED_W, y + settings.LED_H],
                    rounding=6,
                    color=color,
                    fill=color,
                    tag=f"led_{name}"
                )
                # name label (top-left inside)
                dpg.draw_text(
                    [x + 5, y + 3],
                    name,
                    color=text_color,
                    size=32,
                    tag=f"led_name_{name}"
                )
                # status text (bottom-right inside)
                dpg.draw_text(
                    [x + 5, y + settings.LED_H-50],
                    label,
                    color=text_color,
                    size=33,
                    tag=f"led_status_{name}"
                )
                
    # Abort modal screen
    with dpg.window(label="ABORT WARNING", modal=True, show=False, tag="state_modal", 
                    no_resize=True, width=300, height=120):
        
        abort_tov = dpg.add_text(" ", tag="abort_tov")
        dpg.bind_item_font(abort_tov,settings.xl)


def on_key_released(sender, key):
    global lastCmdTime 
    now = time.time()
    
    if now - lastCmdTime >= 0.1:
        #print(now - lastCmdTime, now , lastCmdTime)
        lastCmdTime = now
        if key == dpg.mvKey_P:
            sw.send_ping()
        
# Setup viewport
dpg.create_viewport(title='Flight Computer Viewer', width=settings.WINDOW_DIM[0], height=settings.WINDOW_DIM[1])
dpg.setup_dearpygui()
dpg.show_viewport()

# ---------------- main loop ----------------
WINDOW_SIZE = 80  # seconds or timestamp units to display
lastTime = 0

try:
    with dpg.handler_registry():
            dpg.add_key_press_handler(callback=on_key_released)
            
    while dpg.is_dearpygui_running():
        if sr.streamTelem.tsy_timestamp == last_timestamp:
            if disconnect_counter > disconnect_timeout:  
                valid_connection = False
            disconnect_counter += 1
        else:
            disconnect_counter = 0    
            valid_connection = True
        
        last_timestamp = sr.streamTelem.tsy_timestamp
        
        frameTime = time.time()
        # Append latest data
        timestamps.append(sr.streamTelem.tsy_timestamp/1000)
        pt1_list.append(sr.streamTelem.pt1)
        pt4_list.append(sr.streamTelem.pt4)
        
        
            
        
        dpg.set_value("pt1_list", [list(timestamps), list(pt1_list)]) 
        dpg.set_value("pt4_list", [list(timestamps), list(pt4_list)]) 
        all_pressures = list(pt1_list) + list(pt4_list)
        dpg.set_axis_limits("y_axis_pressure", min(all_pressures), max(all_pressures))

        
        # Update x-axis limits to show a moving window
        if timestamps:
            latest = timestamps[-1]
            start = max(latest - WINDOW_SIZE, timestamps[0])  # don't go before first timestamp

            dpg.set_axis_limits("x_axis_busIMUaccel", start, latest)
        updateLiveInfoWindow()
        updateDebugWindow()
        updateStatusBar()    
        update_leds()
        update_error_table()
        updateFillPlot()

        # Render one frame
        dpg.render_dearpygui_frame()
        #time.sleep(1/1000)  # 50 FPS
        
        
        guiLoopTime = (time.time() - frameTime) * 1000000

finally:
    dpg.destroy_context()
