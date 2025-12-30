import dearpygui.dearpygui as dpg #type: ignore
import serial_reader as sr
import time
import struct
from collections import deque
import random
import math

ROTATE_ENABLED = True


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

def load_openrocket_csv_for_dpg(path):
    """
    Load an OpenRocket-style CSV file and return data
    suitable for DearPyGui plotting.

    Returns:
        dict with keys:
            'time'      -> list[float]
            'altitude'  -> list[float]
            'velocity'  -> list[float]
    """

    time = []
    altitude = []
    velocity = []

    with open(path, "r") as f:
        for line in f:
            line = line.strip()

            # Skip comments, events, headers, empty lines
            if not line or line.startswith("#"):
                continue

            # Expect: time, altitude, vertical velocity
            parts = line.split(",")

            if len(parts) != 3:
                continue  # safety

            try:
                t = float(parts[0])
                alt = float(parts[1])
                vel = float(parts[2])
            except ValueError:
                continue  # skip malformed rows

            time.append(t)
            altitude.append(alt)
            velocity.append(vel)

    return {
        "time": time,
        "altitude": altitude,
        "velocity": velocity,
    }

def draw_cylinder(radius, z0, z1, segments, color):
    for i in range(segments):
        a0 = 2 * math.pi * i / segments
        a1 = 2 * math.pi * (i + 1) / segments

        x0, y0 = radius * math.cos(a0), radius * math.sin(a0)
        x1, y1 = radius * math.cos(a1), radius * math.sin(a1)

        v00 = [x0, y0, z0]
        v01 = [x1, y1, z0]
        v10 = [x0, y0, z1]
        v11 = [x1, y1, z1]

        dpg.draw_triangle(v00, v01, v10, fill=color, color=color)
        dpg.draw_triangle(v01, v11, v10, fill=color, color=color)

def draw_cone(radius, z_base, z_tip, segments, color):
    tip = [0, 0, z_tip]

    for i in range(segments):
        a0 = 2 * math.pi * i / segments
        a1 = 2 * math.pi * (i + 1) / segments

        v0 = [radius * math.cos(a0), radius * math.sin(a0), z_base]
        v1 = [radius * math.cos(a1), radius * math.sin(a1), z_base]

        dpg.draw_triangle(v0, v1, tip, fill=color, color=color)

def draw_fin_triangle(angle_deg, body_radius, z0, z1, span, color):
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)

    def rot(x, y, z):
        return [c*x - s*y, s*x + c*y, z]

    v0 = rot(body_radius,        0, z1)
    v1 = rot(body_radius,        0, z0)
    v2 = rot(body_radius + span, 0, z0)

    # Front face
    dpg.draw_triangle(v0, v1, v2, fill=color, color=color)
    # Back face (reverse winding)
    dpg.draw_triangle(v2, v1, v0, fill=color, color=color)

def update_rocket():
    view = dpg.create_fps_matrix([0,0,40], 0, 0)
    proj = dpg.create_perspective_matrix(math.radians(45), 1, 0.1, 100)

    rot = dpg.get_item_user_data("rocket_node")

    if ROTATE_ENABLED:
        rot[0] += 0.5
        rot[1] += 1.0
        rot[2] += 0.2

    model = (
        dpg.create_rotation_matrix(math.radians(rot[2]), [0,0,1]) *
        dpg.create_rotation_matrix(math.radians(rot[1]), [0,1,0]) *
        dpg.create_rotation_matrix(math.radians(rot[0]), [1,0,0])
    )

    dpg.apply_transform("rocket_node", proj * view * model)
    dpg.set_item_user_data("rocket_node", rot)

def toggle_rotation(sender):
    global ROTATE_ENABLED
    ROTATE_ENABLED = not ROTATE_ENABLED
    dpg.set_item_label(sender, "Stop Rotation" if ROTATE_ENABLED else "Start Rotation")

def draw_axis_arrows(center=[0,0,0], length=3.0, thickness=0.05):
    """
    Draws 3 arrows from center along X, Y, Z axes.
    X: Red, Y: Green, Z: Blue
    """
    cx, cy, cz = center

    # Arrow tips (a small triangle at the end)
    tip_size = 0

    axes = {
        "X": ([length, 0, 0], [255, 0, 0, 255]),
        "Y": ([0, length, 0], [0, 255, 0, 255]),
        "Z": ([0, 0, length], [0, 0, 255, 255])
    }

    for axis, (vec, color) in axes.items():
        ex, ey, ez = vec
        # Draw main shaft
        dpg.draw_line([cx, cy, cz], [cx + ex, cy + ey, cz + ez], color=color, thickness=thickness)
        # Arrowhead (triangle)
        # Pick two points perpendicular to the axis for a simple triangle
        if axis == "X":
            v0 = [cx + ex, cy + ey, cz + ez]
            v1 = [cx + ex - tip_size, cy + tip_size, cz + tip_size]
            v2 = [cx + ex - tip_size, cy - tip_size, cz - tip_size]
        elif axis == "Y":
            v0 = [cx + ex, cy + ey, cz + ez]
            v1 = [cx + tip_size, cy + ey - tip_size, cz + tip_size]
            v2 = [cx - tip_size, cy + ey - tip_size, cz - tip_size]
        else:  # Z
            v0 = [cx + ex, cy + ey, cz + ez]
            v1 = [cx + tip_size, cy + tip_size, cz + ez - tip_size]
            v2 = [cx - tip_size, cy - tip_size, cz + ez - tip_size]

        dpg.draw_triangle(v0, v1, v2, fill=color, color=color)
        dpg.draw_triangle(v1, v1, v0, fill=color, color=color)

def updateDataWindow():
    dpg.set_value("comp_time", f"Computer Time: {time.localtime().tm_hour}:{time.localtime().tm_min}:{time.localtime().tm_sec}")
    dpg.set_value("tov", f"Flight Computer Uptime: 00:00") # make this the serial timestamp
    dpg.set_value("fc_flight_time", f"Flight Time: 00:00")
    dpg.set_value("fc_state", f"State: Burnout")
    dpg.set_value("max_accel", f"Max Accel: 4G")
    dpg.set_value("max_vel", f"Max Velocity: 0.57 Mach")
    dpg.set_value("coords", f"Lat: 37.15248 Long: 118.65546")

def updateOrientationWindow():
    dpg.set_value("orientation", f"X: 0.10 deg Y: 0.01 deg Z = 89.97 deg")
    
openRkt_Data = load_openrocket_csv_for_dpg("Assets/Simulation Imperial.csv")

dpg.create_context()
WINDOW_DIM = (1920,1080)

with dpg.font_registry():
    small = dpg.add_font("Assets/RobotoMono-Regular.ttf", 14)
    default = dpg.add_font("Assets/RobotoMono-Regular.ttf", 18)
    medium = dpg.add_font("Assets/RobotoMono-Regular.ttf", 25)
    large = dpg.add_font("Assets/RobotoMono-Regular.ttf", 30)
    xl = dpg.add_font("Assets/RobotoMono-Regular.ttf", 40)
    
dpg.bind_font(default)

with dpg.window(label="Flight Computer Viewer", width=WINDOW_DIM[0], height=WINDOW_DIM[1], no_title_bar=True, no_move=True):
    with dpg.tab_bar(label="Main Tabs"): # Create the tab bar 
        with dpg.tab(label="Flight Monitor"):

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

            y_offset = 32
            x_offset = 5

            # Child window size and positions:
            EVENTS_WINDOW_SIZE = (450, 470)
            EVENTS_WINDOW_POS = (WINDOW_DIM[0]-EVENTS_WINDOW_SIZE[0]-x_offset, 0+y_offset)

            ORIENT_WINDOW_SIZE = (450,50)
            ORIENT_WINDOW_POS = (WINDOW_DIM[0]-EVENTS_WINDOW_SIZE[0]-x_offset, EVENTS_WINDOW_SIZE[1])

            PLOT3D_WINDOW_SIZE = (450, 450)
            PLOT3D_WINDOW_POS = (WINDOW_DIM[0]-EVENTS_WINDOW_SIZE[0]-x_offset, EVENTS_WINDOW_SIZE[1]+ORIENT_WINDOW_SIZE[1])
        
            DATA_WINDOW_POS = (800, 0+y_offset)
            DATA_WINDOW_SIZE = (WINDOW_DIM[0]-EVENTS_WINDOW_SIZE[0]-DATA_WINDOW_POS[0]-x_offset, 450)

            # Events window
            with dpg.child_window(width=EVENTS_WINDOW_SIZE[0], height=EVENTS_WINDOW_SIZE[1], pos=EVENTS_WINDOW_POS):
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
                    btn = dpg.add_button(label="    ", parent=row_id, callback=_log)
                    dpg.bind_item_theme(btn, theme_tag)

                    # Event text
                    txt_event = dpg.add_text(theme_tag, parent=row_id)
                    dpg.bind_item_font(txt_event, large)

                    # Time text
                    txt_time = dpg.add_text(f"000.00s", parent=row_id)
                    dpg.bind_item_font(txt_time, large)
                    
            # Plots
            with dpg.plot(label="Altitude vs Time", width=800, height=400, pos=[0,0+y_offset]):
                dpg.add_plot_legend()
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)") # *******  will this work with updating time?
                with dpg.plot_axis(dpg.mvYAxis, label="Altitude [ft]"):
                    dpg.set_axis_limits(dpg.last_item(), 0, max(openRkt_Data["altitude"])+450)
                    dpg.add_line_series([], [], label="Realtime Alt", tag="Altitude")
                    dpg.add_line_series(openRkt_Data["time"], openRkt_Data["altitude"], label="Sim Alt")

            with dpg.plot(label="Velocity vs Time", width=800, height=400, pos=[0,0+y_offset+400]):
                dpg.add_plot_legend()
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)") # *******  will this work with updating time?
                with dpg.plot_axis(dpg.mvYAxis, label="Velocity (ft/s)"):
                    dpg.set_axis_limits(dpg.last_item(), min(openRkt_Data["velocity"])-20, max(openRkt_Data["velocity"])+150)
                    # **** add realtime velocity
                    dpg.add_line_series(openRkt_Data["time"], openRkt_Data["velocity"], label="Sim Vel")

            # Axis Orientation Readout
            with dpg.child_window(label="Rocket Orientation Readout", width=ORIENT_WINDOW_SIZE[0], height=ORIENT_WINDOW_SIZE[1], pos=ORIENT_WINDOW_POS):
                # Computer time
                txt_orientation = dpg.add_text(" ", tag="orientation")
                dpg.bind_item_font(txt_orientation, medium)

            # 3D Orientation Plot
            with dpg.child_window(label="Rocket Orientation", width=PLOT3D_WINDOW_SIZE[0], height=PLOT3D_WINDOW_SIZE[1], pos=PLOT3D_WINDOW_POS):
                """
                +Z = forward (nose direction)
                -Z = aft (fins)
                +X = right
                +Y = up
                """
                #dpg.add_button(label="Stop Rotation",callback=toggle_rotation)

                with dpg.drawlist(width=PLOT3D_WINDOW_SIZE[0], height=PLOT3D_WINDOW_SIZE[1]-16, tag="rocket_drawlist"):
                    with dpg.item_handler_registry(tag="rocket_handler"):
                        dpg.add_item_visible_handler(callback=lambda: update_rocket())

                    dpg.bind_item_handler_registry("rocket_drawlist", "rocket_handler")
                    with dpg.draw_layer(
                        depth_clipping=False,
                        cull_mode=dpg.mvCullMode_Back,
                        perspective_divide=True
                    ):
                        dpg.set_clip_space(
                            dpg.last_item(),
                            0, 0, PLOT3D_WINDOW_SIZE[0], PLOT3D_WINDOW_SIZE[1],
                            -1.0, 1.0
                        )

                        with dpg.draw_node(tag="rocket_node", user_data=[0,0,0]):
                            # In inches **************************** add to config file
                            IN_BODY_RADIUS   = 2
                            IN_RKT_LENGTH    = 105
                            IN_NOSE_LENGTH   = 20
                            IN_FIN_SPAN      = 6.8
                            IN_FIN_HEIGHT    = 7

                            SEGMENTS         = 12
                            scale = 8

                            # Convert to window size scale
                            
                            BODY_RADIUS   = IN_BODY_RADIUS / scale
                            NOSE_LENGTH   = IN_NOSE_LENGTH / scale
                            BODY_LENGTH   = (IN_RKT_LENGTH / scale) - NOSE_LENGTH
                            FIN_SPAN      = IN_FIN_SPAN / scale
                            FIN_HEIGHT    = IN_FIN_HEIGHT / scale
                            

                            z_body_base = -(BODY_LENGTH+FIN_HEIGHT)/2
                            z_body_top  =  (BODY_LENGTH+FIN_HEIGHT)/2

                            # Body
                            draw_cylinder(
                                radius=BODY_RADIUS,
                                z0=z_body_base,
                                z1=z_body_top,
                                segments=SEGMENTS,
                                color=[200,200,200,200]
                            )

                            # Nose cone
                            draw_cone(
                                radius=BODY_RADIUS,
                                z_base=z_body_top,
                                z_tip=z_body_top + NOSE_LENGTH,
                                segments=SEGMENTS,
                                color=[220,50,50,200]
                            )

                            # Fins
                            fin_z0 = z_body_base
                            fin_z1 = z_body_base + FIN_HEIGHT

                            for a in [0, 90, 180, 270]:
                                draw_fin_triangle(
                                    a,
                                    BODY_RADIUS,
                                    fin_z0,
                                    fin_z1,
                                    FIN_SPAN,
                                    [50, 50, 220, 200]
                                )

                            draw_axis_arrows(center=[0,0,0], length=3.0, thickness=3.0)

            # Data Window
            with dpg.child_window(label="Data Readout", width=DATA_WINDOW_SIZE[0], height=DATA_WINDOW_SIZE[1], pos=DATA_WINDOW_POS):
                
                # Computer time
                txt_comp_time = dpg.add_text(" ", tag="comp_time")
                dpg.bind_item_font(txt_comp_time, xl)

                # TOV
                txt_tov = dpg.add_text(" ", tag="tov")
                dpg.bind_item_font(txt_tov, xl)

                # Flight Time
                txt_fc_flight_time = dpg.add_text(" ", tag="fc_flight_time")
                dpg.bind_item_font(txt_fc_flight_time, xl)

                # Flight Computer State
                txt_fc_state = dpg.add_text(" ", tag="fc_state")
                dpg.bind_item_font(txt_fc_state, xl)

                # Max Accel
                txt_max_accel = dpg.add_text(" ", tag="max_accel")
                dpg.bind_item_font(txt_max_accel, xl)

                # Flight Velocity
                txt_max_vel = dpg.add_text(" ", tag="max_vel")
                dpg.bind_item_font(txt_max_vel, xl)

                # Coordinates
                txt_coords = dpg.add_text(" ", tag="coords")
                dpg.bind_item_font(txt_coords, xl)

            # Map Window
            #with dpg.child_window(label="Data Readout", width=DATA_WINDOW_SIZE[0], height=DATA_WINDOW_SIZE[1], pos=DATA_WINDOW_POS):
            #    pass

        with dpg.tab(label="Bus Info"): 
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
                                        
        with dpg.tab(label="IMU Plots"): 
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

        with dpg.tab(label="Serial Monitor"):    
            pass

# Setup viewport
dpg.create_viewport(title='Flight Computer Viewer', width=2000, height=1000)
dpg.setup_dearpygui()
dpg.show_viewport()

# ---------------- main loop ----------------
WINDOW_SIZE = 10  # seconds or timestamp units to display
lastTime = 0
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
        
        dpg.set_value("Altitude", [list(timestamps), list(altitudeM)]) 
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
        
        
        if time.time() - lastTime > 5:
            random_key = random.choice(list(events.keys()))
            events[random_key] = not events[random_key]  # new value
            lastTime = time.time()
            #print(f"updated {random_key} at {lastTime}")

        updateOrientationWindow()
        updateDataWindow()
        # Update x-axis limits to show a moving window
        if timestamps:
            latest = timestamps[-1]
            start = max(latest - WINDOW_SIZE, timestamps[0])  # don't go before first timestamp

            dpg.set_axis_limits("x_axis_busIMUaccel", start, latest)
            dpg.set_axis_limits("x_axis_busIMUgyro", start, latest)
            dpg.set_axis_limits("x_axis_busIMUmag", start, latest)

        # Render one frame
        dpg.render_dearpygui_frame()
        time.sleep(1/50)  # 50 FPS

finally:
    dpg.destroy_context()
