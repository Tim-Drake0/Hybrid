import dearpygui.dearpygui as dpg #type: ignore
import serial_reader as sr
import time
import struct
from collections import deque


class dpgVariable:
    plotBuffer = 1


MAX_POINTS = 2000  # number of points shown in plot

# Get current timestamp as starting point
start_timestamp = sr.busPwr.timestamp

# rolling buffers, pre-filled with starting timestamp
timestamps = deque([start_timestamp], maxlen=MAX_POINTS)
battVolts = deque([sr.busPwr.battVolts], maxlen=MAX_POINTS)
voltage3V = deque([sr.busPwr.voltage3V], maxlen=MAX_POINTS)
voltage5V = deque([sr.busPwr.voltage5V], maxlen=MAX_POINTS)
temperatureC = deque([sr.busBME280.temperatureC], maxlen=MAX_POINTS)
pressurePasc = deque([sr.busBME280.pressurePasc], maxlen=MAX_POINTS)
humidityRH = deque([sr.busBME280.humidityRH], maxlen=MAX_POINTS)
altitudeM = deque([sr.busBME280.altitudeM], maxlen=MAX_POINTS)
accelx = deque([sr.busLSM9DS1.accelx], maxlen=MAX_POINTS)
accely = deque([sr.busLSM9DS1.accely ], maxlen=MAX_POINTS)
accelz = deque([sr.busLSM9DS1.accelz ], maxlen=MAX_POINTS)
magx = deque([sr.busLSM9DS1.magx], maxlen=MAX_POINTS)
magy = deque([sr.busLSM9DS1.magy], maxlen=MAX_POINTS)
magz = deque([sr.busLSM9DS1.magz], maxlen=MAX_POINTS)
gyrox = deque([sr.busLSM9DS1.gyrox], maxlen=MAX_POINTS)
gyroy = deque([sr.busLSM9DS1.gyroy], maxlen=MAX_POINTS)
gyroz = deque([sr.busLSM9DS1.gyroz], maxlen=MAX_POINTS)
highG_accelx = deque([sr.busADXL375.highG_accelx], maxlen=MAX_POINTS)
highG_accely = deque([sr.busADXL375.highG_accely], maxlen=MAX_POINTS)
highG_accelz = deque([sr.busADXL375.highG_accelz], maxlen=MAX_POINTS)


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
        
def _add_config_options(item, columns, *names, **kwargs):
    if columns == 1:
        if 'before' in kwargs:
            for name in names:
                dpg.add_checkbox(label=name, callback=_config, user_data=item, before=kwargs['before'], default_value=dpg.get_item_configuration(item)[name])
        else:
            for name in names:
                dpg.add_checkbox(label=name, callback=_config, user_data=item, default_value=dpg.get_item_configuration(item)[name])
    else:
        if 'before' in kwargs:
            dpg.push_container_stack(dpg.add_table(header_row=False, before=kwargs['before']))
        else:
            dpg.push_container_stack(dpg.add_table(header_row=False))

        for i in range(columns):
            dpg.add_table_column()

        for i in range((len(names)+(columns - 1))//columns):
            with dpg.table_row():
                for j in range(columns):
                    if (i*columns + j) >= len(names): 
                        break
                    dpg.add_checkbox(label=names[i*columns + j], 
                                        callback=_config, user_data=item, 
                                        default_value=dpg.get_item_configuration(item)[names[i*columns + j]])
        dpg.pop_container_stack()
        
def _log(sender, app_data, user_data):
    print(f"sender: {sender}, \t app_data: {app_data}, \t user_data: {user_data}")

dpg.create_context()
WINDOW_DIM = (1920,1000)
with dpg.window(label="Serial Data Plotter", width=WINDOW_DIM[0], height=WINDOW_DIM[1]):
    with dpg.tab_bar(label="Main Tabs"): # Create the tab bar   
        with dpg.tab(label="Bus Info"): # First tab
            with dpg.table(header_row=True, resizable=True, delay_search=True,
                        borders_outerH=True, borders_innerV=True, borders_outerV=True, row_background=True) as table_id:
                dpg.add_table_column(label="busPWR")
                
                dpg.add_table_column(label="busBME280")
                dpg.add_table_column(label="busLSM9DS1")
                dpg.add_table_column(label="busADXL375")
                with dpg.table_row():
                    dpg.add_text(f"TOV: {round(sr.busPwr.timestamp, 3)}", tag="busPwr_TOV")
                    dpg.add_text(f"TOV: {round(sr.busBME280.timestamp, 3)}", tag="busBME280_TOV") 
                    dpg.add_text(f"TOV: {round(sr.busLSM9DS1.timestamp, 3)}", tag="busLSM9DS1_TOV") 
                    dpg.add_text(f"TOV: {round(sr.busADXL375.timestamp, 3)}", tag="busADXL375_TOV")
                    

                with dpg.table_row():
                    # Nested table inside the "Details" cell
                    for bus_name, bus_info in sr.buses.items():
                        with dpg.child_window(width=WINDOW_DIM[0]/4, height=WINDOW_DIM[1]-102):
                            with dpg.table(header_row=False, resizable=True,row_background=False):
                                dpg.add_table_column(label="Name")
                                dpg.add_table_column(label="Val")
                                dpg.add_table_column(label="Unit")
                                dpg.add_table_column(label=" ")
                                

                                for field_name, field_props in bus_info['data'].items():
                                    with dpg.table_row():
                                        dpg.add_text(field_name)
                                        dpg.add_text(" ", tag=field_name)
                                        dpg.add_text(field_props['unit'])
                                        dpg.add_input_text(callback=_log) # add function that overrides all variables when enter is hit
                                        
   
        with dpg.tab(label="IMU Plots"): # Second tab
            with dpg.plot(label="busIMU Accel", width=1990, height=300, pos=[0,45]):
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

            with dpg.plot(label="busIMU Gyro", width=1990, height=300, pos=[0,345]):
                dpg.add_plot_legend()
                with dpg.plot_axis(dpg.mvXAxis, label="Timestamp", tag="x_axis_busIMUgyro"):
                    pass
                with dpg.plot_axis(dpg.mvYAxis, label="dps"):
                    dpg.set_axis_limits(dpg.last_item(), -100, 100)
                    dpg.add_line_series([], [], label="gyrox", tag="Gyrox")
                    dpg.add_line_series([], [], label="gyroy", tag="Gyroy")
                    dpg.add_line_series([], [], label="gyroz", tag="Gyroz")

            with dpg.plot(label="busIMU Mag", width=1990, height=300, pos=[0,645]):
                dpg.add_plot_legend()
                with dpg.plot_axis(dpg.mvXAxis, label="Timestamp", tag="x_axis_busIMUmag"):
                    pass
                with dpg.plot_axis(dpg.mvYAxis, label="dps"):
                    dpg.set_axis_limits(dpg.last_item(), -2, 2)
                    dpg.add_line_series([], [], label="magx", tag="Magx")
                    dpg.add_line_series([], [], label="magy", tag="Magy")
                    dpg.add_line_series([], [], label="magz", tag="Magz")        

# Setup viewport
dpg.create_viewport(title='Serial Telemetry', width=2000, height=1000)
dpg.setup_dearpygui()
dpg.show_viewport()

# ---------------- Custom main loop ----------------
WINDOW_SIZE = 10  # seconds or timestamp units to display

try:
    while dpg.is_dearpygui_running():
        # Append latest data
        timestamps.append(sr.busLSM9DS1.timestamp)
        battVolts.append(sr.busPwr.battVolts)
        voltage3V.append(sr.busPwr.voltage3V)
        voltage5V.append(sr.busPwr.voltage5V)
        temperatureC.append(sr.busBME280.temperatureC) 
        pressurePasc.append(sr.busBME280.pressurePasc) 
        humidityRH.append(sr.busBME280.humidityRH) 
        altitudeM.append(sr.busBME280.altitudeM) 
        accelx.append(sr.busLSM9DS1.accelx) 
        accely.append(sr.busLSM9DS1.accely ) 
        accelz.append(sr.busLSM9DS1.accelz ) 
        magx.append(sr.busLSM9DS1.magx) 
        magy.append(sr.busLSM9DS1.magy) 
        magz.append(sr.busLSM9DS1.magz) 
        gyrox.append(sr.busLSM9DS1.gyrox) 
        gyroy.append(sr.busLSM9DS1.gyroy) 
        gyroz.append(sr.busLSM9DS1.gyroz) 
        highG_accelx.append(sr.busADXL375.highG_accelx) 
        highG_accely.append(sr.busADXL375.highG_accely) 
        highG_accelz.append(sr.busADXL375.highG_accelz) 
        
        dpg.set_value("battVolts",      round(sr.busPwr.battVolts,3))
        dpg.set_value("voltage3V",      round(sr.busPwr.voltage3V,3))
        dpg.set_value("voltage5V",      round(sr.busPwr.voltage5V,3))
        dpg.set_value("temperatureC",   round(sr.busBME280.temperatureC,3))
        dpg.set_value("pressurePasc",   round(sr.busBME280.pressurePasc,3))
        dpg.set_value("humidityRH",     round(sr.busBME280.humidityRH,3))
        dpg.set_value("altitudeM",      round(sr.busBME280.altitudeM,3))
        dpg.set_value("accelx",         round(sr.busLSM9DS1.accelx,5)) 
        dpg.set_value("accely",         round(sr.busLSM9DS1.accely,5)) 
        dpg.set_value("accelz",         round(sr.busLSM9DS1.accelz,5)) 
        dpg.set_value("magx",           round(sr.busLSM9DS1.magx,3)) 
        dpg.set_value("magy",           round(sr.busLSM9DS1.magy,3)) 
        dpg.set_value("magz",           round(sr.busLSM9DS1.magz,3)) 
        dpg.set_value("gyrox",          round(sr.busLSM9DS1.gyrox,3)) 
        dpg.set_value("gyroy",          round(sr.busLSM9DS1.gyroy,3)) 
        dpg.set_value("gyroz",          round(sr.busLSM9DS1.gyroz,3)) 
        dpg.set_value("highG_accelx",   round(sr.busADXL375.highG_accelx,3)) 
        dpg.set_value("highG_accely",   round(sr.busADXL375.highG_accely,3)) 
        dpg.set_value("highG_accelz",   round(sr.busADXL375.highG_accelz,3)) 
        
        dpg.set_value("busPwr_TOV",         f"TOV: {round(sr.busPwr.timestamp, 3)}") 
        dpg.set_value("busBME280_TOV",      f"TOV: {round(sr.busBME280.timestamp, 3)}") 
        dpg.set_value("busLSM9DS1_TOV",     f"TOV: {round(sr.busLSM9DS1.timestamp, 3)}") 
        dpg.set_value("busADXL375_TOV",     f"TOV: {round(sr.busADXL375.timestamp, 3)}") 
        

        dpg.set_value("Accelx", [list(timestamps), list(accelx)]) 
        dpg.set_value("Accely", [list(timestamps), list(accely)]) 
        dpg.set_value("Accelz", [list(timestamps), list(accelz)]) 
        dpg.set_value("Magx", [list(timestamps), list(magx)]) 
        dpg.set_value("Magy", [list(timestamps), list(magy)]) 
        dpg.set_value("Magz", [list(timestamps), list(magz)]) 
        dpg.set_value("Gyrox", [list(timestamps), list(gyrox)]) 
        dpg.set_value("Gyroy", [list(timestamps), list(gyroy)]) 
        dpg.set_value("Gyroz", [list(timestamps), list(gyroz)]) 
        dpg.set_value("HighG_accelx", [list(timestamps), list(highG_accelx)]) 
        dpg.set_value("HighG_accely", [list(timestamps), list(highG_accely)]) 
        dpg.set_value("HighG_accelz", [list(timestamps), list(highG_accelz)]) 
        
        
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
