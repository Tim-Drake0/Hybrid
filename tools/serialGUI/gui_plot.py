import dearpygui.dearpygui as dpg
import serial_reader as sr
import time
from collections import deque

MAX_POINTS = 2000  # number of points shown in plot

# Get current timestamp as starting point
start_timestamp = sr.latest_frame.timestamp

# rolling buffers, pre-filled with starting timestamp
timestamps = deque([start_timestamp], maxlen=MAX_POINTS)
volt_batt = deque([sr.latest_frame.volt_batt], maxlen=MAX_POINTS)
volt_3v = deque([sr.latest_frame.volt_3v], maxlen=MAX_POINTS)
volt_5v = deque([sr.latest_frame.volt_5v], maxlen=MAX_POINTS)
temp = deque([sr.latest_frame.temp], maxlen=MAX_POINTS)
pressure = deque([sr.latest_frame.pressure], maxlen=MAX_POINTS)
humidity = deque([sr.latest_frame.humidity], maxlen=MAX_POINTS)
altitude = deque([sr.latest_frame.altitude], maxlen=MAX_POINTS)
accelx = deque([sr.latest_frame.accelx], maxlen=MAX_POINTS)
accely  = deque([sr.latest_frame.accely ], maxlen=MAX_POINTS)
accelz  = deque([sr.latest_frame.accelz ], maxlen=MAX_POINTS)
magx = deque([sr.latest_frame.magx], maxlen=MAX_POINTS)
magy = deque([sr.latest_frame.magy], maxlen=MAX_POINTS)
magz = deque([sr.latest_frame.magz], maxlen=MAX_POINTS)
gyrox = deque([sr.latest_frame.gyrox], maxlen=MAX_POINTS)
gyroy = deque([sr.latest_frame.gyroy], maxlen=MAX_POINTS)
gyroz = deque([sr.latest_frame.gyroz], maxlen=MAX_POINTS)
highG_accelx = deque([sr.latest_frame.highG_accelx], maxlen=MAX_POINTS)
highG_accely = deque([sr.latest_frame.highG_accely], maxlen=MAX_POINTS)
highG_accelz = deque([sr.latest_frame.highG_accelz], maxlen=MAX_POINTS)

dpg.create_context()

with dpg.window(label="Serial Data Plotter", width=2000, height=1000):
            
    with dpg.plot(label="busIMU Accel", width=2000, height=300, pos=[0,15]):
        dpg.add_plot_legend()
        with dpg.plot_axis(dpg.mvXAxis, label="Timestamp", tag="x_axis_busIMUaccel"):
            pass
        with dpg.plot_axis(dpg.mvYAxis, label="m/s^2"):
            dpg.set_axis_limits(dpg.last_item(), -20, 20)
            dpg.add_line_series([], [], label="accelx", tag="accelx")
            dpg.add_line_series([], [], label="accely", tag="accely")
            dpg.add_line_series([], [], label="accelz", tag="accelz")
            dpg.add_line_series([], [], label="highG_accelx", tag="highG_accelx")
            dpg.add_line_series([], [], label="highG_accely", tag="highG_accely")
            dpg.add_line_series([], [], label="highG_accelz", tag="highG_accelz")
            
    with dpg.plot(label="busIMU Gyro", width=2000, height=300, pos=[0,315]):
        dpg.add_plot_legend()
        with dpg.plot_axis(dpg.mvXAxis, label="Timestamp", tag="x_axis_busIMUgyro"):
            pass
        with dpg.plot_axis(dpg.mvYAxis, label="dps"):
            dpg.set_axis_limits(dpg.last_item(), -20, 20)
            dpg.add_line_series([], [], label="gyrox", tag="gyrox")
            dpg.add_line_series([], [], label="gyroy", tag="gyroy")
            dpg.add_line_series([], [], label="gyroz", tag="gyroz")
            
    with dpg.plot(label="busIMU Mag", width=2000, height=300, pos=[0,615]):
        dpg.add_plot_legend()
        with dpg.plot_axis(dpg.mvXAxis, label="Timestamp", tag="x_axis_busIMUmag"):
            pass
        with dpg.plot_axis(dpg.mvYAxis, label="dps"):
            dpg.set_axis_limits(dpg.last_item(), -40, 40)
            dpg.add_line_series([], [], label="magx", tag="magx")
            dpg.add_line_series([], [], label="magy", tag="magy")
            dpg.add_line_series([], [], label="magz", tag="magz")

# Setup viewport
dpg.create_viewport(title='Serial Telemetry', width=2000, height=1000)
dpg.setup_dearpygui()
dpg.show_viewport()

# ---------------- Custom main loop ----------------
WINDOW_SIZE = 10  # seconds or timestamp units to display

try:
    while dpg.is_dearpygui_running():
        # Append latest data
        timestamps.append(sr.latest_frame.timestamp)
        volt_batt.append(sr.latest_frame.volt_batt)
        volt_3v.append(sr.latest_frame.volt_3v)
        volt_5v.append(sr.latest_frame.volt_5v)
        temp.append(sr.latest_frame.temp) 
        pressure.append(sr.latest_frame.pressure) 
        humidity.append(sr.latest_frame.humidity) 
        altitude.append(sr.latest_frame.altitude) 
        accelx.append(sr.latest_frame.accelx) 
        accely .append(sr.latest_frame.accely ) 
        accelz .append(sr.latest_frame.accelz ) 
        magx.append(sr.latest_frame.magx) 
        magy.append(sr.latest_frame.magy) 
        magz.append(sr.latest_frame.magz) 
        gyrox.append(sr.latest_frame.gyrox) 
        gyroy.append(sr.latest_frame.gyroy) 
        gyroz.append(sr.latest_frame.gyroz) 
        highG_accelx.append(sr.latest_frame.highG_accelx) 
        highG_accely.append(sr.latest_frame.highG_accely) 
        highG_accelz.append(sr.latest_frame.highG_accelz) 
        
        # Update line series
        # dpg.set_value("volt_batt", [list(timestamps), list(volt_batt)])
        # dpg.set_value("volt_3v", [list(timestamps), list(volt_3v)])
        # dpg.set_value("volt_5v", [list(timestamps), list(volt_5v)])
        # dpg.set_value("temp", [list(timestamps), list(temp)]) 
        # dpg.set_value("pressure", [list(timestamps), list(pressure)]) 
        # dpg.set_value("humidity", [list(timestamps), list(humidity)]) 
        # dpg.set_value("altitude", [list(timestamps), list(altitude)]) 
        dpg.set_value("accelx", [list(timestamps), list(accelx)]) 
        dpg.set_value("accely", [list(timestamps), list(accely)]) 
        dpg.set_value("accelz", [list(timestamps), list(accelz)]) 
        dpg.set_value("magx", [list(timestamps), list(magx)]) 
        dpg.set_value("magy", [list(timestamps), list(magy)]) 
        dpg.set_value("magz", [list(timestamps), list(magz)]) 
        dpg.set_value("gyrox", [list(timestamps), list(gyrox)]) 
        dpg.set_value("gyroy", [list(timestamps), list(gyroy)]) 
        dpg.set_value("gyroz", [list(timestamps), list(gyroz)]) 
        dpg.set_value("highG_accelx", [list(timestamps), list(highG_accelx)]) 
        dpg.set_value("highG_accely", [list(timestamps), list(highG_accely)]) 
        dpg.set_value("highG_accelz", [list(timestamps), list(highG_accelz)]) 
        
        
        # Update x-axis limits to show a moving window
        if timestamps:
            latest = timestamps[-1]
            start = max(latest - WINDOW_SIZE, timestamps[0])  # don't go before first timestamp
            
            #dpg.set_axis_limits("x_axis_busPWR", start, latest)
            dpg.set_axis_limits("x_axis_busIMUaccel", start, latest)
            dpg.set_axis_limits("x_axis_busIMUgyro", start, latest)
            dpg.set_axis_limits("x_axis_busIMUmag", start, latest)

        # Render one frame
        dpg.render_dearpygui_frame()
        time.sleep(1/50)  # 50 FPS

finally:
    dpg.destroy_context()
