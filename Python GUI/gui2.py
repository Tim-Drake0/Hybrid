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
timestamps = deque([sr.streamTelem.timestamp], maxlen=MAX_POINTS)

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
        color = [0, 255, 0]
        label = "CONNECTED"
        pos = [35, draw_y // 2 - 15]
    else: 
        color = [255, 0, 0]
        label = "DISCONNECTED"
        pos = [15, draw_y // 2 - 15]
        
    dpg.configure_item("conn_status_rect", color=color, fill=color)
    dpg.configure_item("conn_status_text", text=label, pos=pos)
    
    
    
    stampSecs = sr.streamTelem.timestamp / 1000000
    tov_min = (stampSecs / 60) % 60
    tov_hour = round(round(stampSecs / 60, 0) / 60, 0)
    tov_sec = stampSecs % 60
    dpg.set_value("tov", f"{int(tov_hour):02d}:{int(tov_min):02d}:{int(tov_sec):02d}") # make this the serial timestamp
    
    #dpg.set_value("fc_flight_time", f"Flight Time: 00:00")
    #dpg.set_value("fc_state", f"State: Burnout")
    #dpg.set_value("max_accel", f"Max Accel: 4G")
    #dpg.set_value("max_vel", f"Max Velocity: 0.57 Mach")
    #dpg.set_value("coords", f"Lat: 37.15248 Long: 118.65546")
    #dpg.set_value("sensBITs", f"Sensor BITs: {sr.streamTelem.sensorsBIT:08b}")
                  
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
    
    with dpg.child_window(width=settings.STATUS_BAR_SIZE[0], height=settings.STATUS_BAR_SIZE[1], no_scrollbar=True):
        with dpg.group(horizontal=True):
            
            _draw_t = 3.0
            draw_size = 20
            draw_spacing = 10
            draw_rounding = draw_size/5.0
            draw_color = [0, 255, 0]
            draw_x = 190
            draw_y = settings.STATUS_BAR_SIZE[1] - 15
            
            with dpg.drawlist(width=draw_x, height=settings.STATUS_BAR_SIZE[1]):
                
                dpg.draw_rectangle([1, 1], [draw_x, draw_y], rounding=draw_rounding, thickness=_draw_t, color=draw_color, fill=(draw_color), tag="conn_status_rect")
                draw_x = draw_x + draw_spacing + draw_size
                
                txt_connection_status = dpg.draw_text(
                    [15, draw_y // 2 - 15], 
                    "CONNECTED",           
                    color=[0, 0, 0],
                    size=30,
                    tag="conn_status_text"   
                )

            # TOV
            txt_tov = dpg.add_text(" ", tag="tov")
            dpg.bind_item_font(txt_tov,settings.xl)
            
    with dpg.child_window(width=settings.INFO_WINDOW_SIZE[0], height=settings.INFO_WINDOW_SIZE[1], pos=settings.INFO_WINDOW_POS, tag="right_window_bus_info", show=True):
        
        txt_tov = dpg.add_text(" ", tag="timestamp")
        
        
        
        
    with dpg.child_window(width=settings.PLOT_WINDOW_SIZE[0], height=settings.PLOT_WINDOW_SIZE[1], pos=settings.PLOT_WINDOW_POS, tag="plot_window", show=True):
                       
        with dpg.plot(label="busIMU Accel", width=settings.INFO_WINDOW_SIZE[0]-16, height=300, pos=[0,45]):
            dpg.add_plot_legend()
            with dpg.plot_axis(dpg.mvXAxis, label="Timestamp", tag="x_axis_busIMUaccel"):
                pass
            with dpg.plot_axis(dpg.mvYAxis, label="m/s^2"):
                dpg.set_axis_limits(dpg.last_item(), -20, 20) 
                dpg.add_line_series([], [], label="accelx", tag="Accelx")
                dpg.add_line_series([], [], label="accely", tag="Accely")
                dpg.add_line_series([], [], label="accelz", tag="Accelz")
                dpg.add_line_series([], [], label="highG_accelx", tag="HighG_accelx")
                dpg.add_line_series([], [], label="highG_accely", tag="HighG_accely")
                dpg.add_line_series([], [], label="highG_accelz", tag="HighG_accelz")
                
                
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
        if sr.streamTelem.timestamp == last_timestamp:
            if disconnect_counter > disconnect_timeout:  
                valid_connection = False
            disconnect_counter += 1
        else:
            disconnect_counter = 0    
            valid_connection = True
        
        last_timestamp = sr.streamTelem.timestamp
        
        frameTime = time.time()
        # Append latest data
        timestamps.append(sr.streamTelem.timestamp/1000)
        
        
        
        dpg.set_value("timestamp",      round(sr.streamTelem.timestamp,3))
        #dpg.set_value("C1",             round(sr.streamTelem.C1,3))
        #dpg.set_value("C2",             round(sr.streamTelem.C2,3))
        #dpg.set_value("loadCell",       round(sr.streamTelem.loadCell,3))
        #dpg.set_value("PT_tank",        round(sr.streamTelem.PT_tank,3))
        #dpg.set_value("battVolts",      round(sr.streamTelem.battVolts,3))
        #dpg.set_value("altitudRSSIeM",  round(sr.streamTelem.RSSI,3))
            
        
        
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
