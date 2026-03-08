import dearpygui.dearpygui as dpg
import serial_reader as sr
import serial_writer as sw
import gui_settings as settings
import time
from collections import deque
import random
import sys
from pathlib import Path
sensor_path = Path(__file__).parent / "Sensor Info"
sys.path.append(str(sensor_path))

ROTATE_ENABLED = True

valid_connection = False
last_timestamp = 0
disconnect_counter = 0
disconnect_timeout = 100 # loops 

class dpgVariable:
    plotBuffer = 1

MAX_POINTS = 2000  # number of points shown in plot
lastCmdTime = 0
# Get current timestamp as starting point

# rolling buffers, pre-filled with starting timestamp
timestamps = deque([sr.streamTelem.tsy_timestamp], maxlen=MAX_POINTS)
pt1_list = deque([sr.streamTelem.pt1], maxlen=MAX_POINTS)

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
    if valid_connection == True:
        conn_color = [0, 255, 0]
        conn_label = "CONNECTED"
        conn_pos = [35, draw_y // 2 - 15]
    else: 
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
    
    stampSecs = sr.streamTelem.tsy_timestamp / 1000
    tov_min = (stampSecs / 60) % 60
    tov_hour = round(round(stampSecs / 60, 0) / 60, 0)
    tov_sec = stampSecs % 60
    dpg.set_value("tov", f"{int(tov_hour):02d}:{int(tov_min):02d}:{int(tov_sec):02d}") # make this the serial timestamp
                  
dpg.create_context()

settings.createFonts()
dpg.bind_font(settings.default)

# Events *********************************************** move to config file
events = {
    "Arm Command": 0,
    "Launch Command": 0,
    "Burnout":0,
    "Main1": 0,
    "Main2": 0,
    "Drogue1": 0,
    "Drogue2": 0,
    "MOV": 0,
    "Vent": 0,
    "Fill": 0,
}

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
        
        dpg.add_text(" ", tag="ctrl_timestamp")
        dpg.add_text(" ", tag="ctrl_RSSI")
        dpg.add_text(" ", tag="daq_timestamp")
        dpg.add_text(" ", tag="daq_RSSI")
        dpg.add_text(" ", tag="tsy_timestamp")
        dpg.add_text(" ", tag="valve_states")
        dpg.add_text(" ", tag="pyro_states")
        dpg.add_text(" ", tag="arm_state")
        dpg.add_text(" ", tag="pt1")
        dpg.add_text(" ", tag="pt2")
        dpg.add_text(" ", tag="pt3")
        dpg.add_text(" ", tag="pt4")
        dpg.add_text(" ", tag="pt5")
        dpg.add_text(" ", tag="pt6")
        dpg.add_text(" ", tag="loadCell")
        dpg.add_text(" ", tag="battVolts")
        dpg.add_text(" ", tag="fiveVolts")
        dpg.add_text(" ", tag="radioVolts")
        
        
        
        
        
    with dpg.child_window(width=settings.PLOT_WINDOW_SIZE[0], height=settings.PLOT_WINDOW_SIZE[1], pos=settings.PLOT_WINDOW_POS, tag="plot_window", show=True):
                       
        with dpg.plot(label="Pressures", width=settings.PLOT_WINDOW_SIZE[0]-16, height=400, pos=[0,45]):
            dpg.add_plot_legend()
            with dpg.plot_axis(dpg.mvXAxis, label="Timestamp", tag="x_axis_busIMUaccel"):
                pass
            with dpg.plot_axis(dpg.mvYAxis, label="PSI", tag="y_axis_pressure"):
                dpg.set_axis_limits(dpg.last_item(), -20, 20) 
                dpg.add_line_series([], [], label="Tank Pressure", tag="pt1_list")
                
                
        # Events window
    with dpg.child_window(width=settings.EVENTS_WINDOW_SIZE[0], height=settings.EVENTS_WINDOW_SIZE[1], pos=settings.EVENTS_WINDOW_POS):
        # Create table
        table_id = dpg.add_table(header_row=False, resizable=True, borders_innerH=True, borders_outerH=False)
        dpg.add_table_column(parent=table_id, init_width_or_weight=25)  # Event
        dpg.add_table_column(parent=table_id, init_width_or_weight=90)  # Button
        dpg.add_table_column(parent=table_id, init_width_or_weight=40)  # Time

        for event, val in events.items():
            if val == 0:
                color = (255,0,0) # red
            elif val == 1:
                color = (0,255,0) # green
            else:
                color = (0,0,255) # blue 

            i = 3
            row_id = dpg.add_table_row(parent=table_id)

            # Button theme
            theme_tag = f"{event}"
            with dpg.theme(tag=theme_tag):
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, color)
                    dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 9)
                    dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 9,9)

            # Add button
            btn = dpg.add_button(label="    ", parent=row_id)
            dpg.bind_item_theme(btn, theme_tag)

            # Event text
            txt_event = dpg.add_text(theme_tag, parent=row_id)
            dpg.bind_item_font(txt_event, settings.large)

            # Time text
            txt_time = dpg.add_text(f"000.00s", parent=row_id)
            dpg.bind_item_font(txt_time, settings.large)

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
WINDOW_SIZE = 10  # seconds or timestamp units to display
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
        
        
        
        # set_value
        dpg.set_value("ctrl_timestamp",  f"Ctrl timestamp: {sr.streamTelem.ctrl_timestamp} ms")
        dpg.set_value("ctrl_RSSI",       f"Ctrl RSSI: {sr.streamTelem.ctrl_RSSI} dBm")
        dpg.set_value("daq_timestamp",   f"DAQ timestamp: {sr.streamTelem.daq_timestamp} ms")
        dpg.set_value("daq_RSSI",        f"DAQ RSSI: {sr.streamTelem.daq_RSSI} dBm")
        dpg.set_value("tsy_timestamp",   f"Teensy timestamp: {sr.streamTelem.tsy_timestamp} ms")
        dpg.set_value("valve_states",    f"Valve states: {sr.streamTelem.valve_states:08b}")
        dpg.set_value("pyro_states",     f"Pyro states: {sr.streamTelem.pyro_states:08b}")
        dpg.set_value("arm_state",       f"Arm state: {sr.streamTelem.arm_state}")
        dpg.set_value("pt1",             f"PT1: {round(sr.streamTelem.pt1, 2)} PSI")
        dpg.set_value("pt2",             f"PT2: {round(sr.streamTelem.pt2, 2)} PSI")
        dpg.set_value("pt3",             f"PT3: {round(sr.streamTelem.pt3, 2)} PSI")
        dpg.set_value("pt4",             f"PT4: {round(sr.streamTelem.pt4, 2)} PSI")
        dpg.set_value("pt5",             f"PT5: {round(sr.streamTelem.pt5, 2)} PSI")
        dpg.set_value("pt6",             f"PT6: {round(sr.streamTelem.pt6, 2)} PSI")
        dpg.set_value("loadCell",        f"Load cell: {round(sr.streamTelem.loadCell, 3)} lbf")
        dpg.set_value("battVolts",       f"Battery voltage: {round(sr.streamTelem.battVolts, 3)} V")
        dpg.set_value("fiveVolts",       f"5V bus voltage: {round(sr.streamTelem.fiveVolts, 3)} V")
        dpg.set_value("radioVolts",      f"Radio voltage: {round(sr.streamTelem.radioVolts, 3)} V")
            
        
        dpg.set_value("pt1_list", [list(timestamps), list(pt1_list)]) 
        dpg.set_axis_limits("y_axis_pressure", min(pt1_list), max(pt1_list))
        
        
        if time.time() - lastTime > 5:
            random_key = random.choice(list(events.keys()))
            events[random_key] = not events[random_key]  # new value
            lastTime = time.time()
            #print(f"updated {random_key} at {lastTime}")

        # Update x-axis limits to show a moving window
        if timestamps:
            latest = timestamps[-1]
            start = max(latest - WINDOW_SIZE, timestamps[0])  # don't go before first timestamp

            dpg.set_axis_limits("x_axis_busIMUaccel", start, latest)
        
        updateStatusBar()    
            

        # Render one frame
        dpg.render_dearpygui_frame()
        #time.sleep(1/1000)  # 50 FPS
        
        
        guiLoopTime = (time.time() - frameTime) * 1000000

finally:
    dpg.destroy_context()
