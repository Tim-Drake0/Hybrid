import dearpygui.dearpygui as dpg
import pandas as pd
from math import sin
import csv
import os
import platform

# Set path based on platform
if platform.system() == "Windows":
    sd_path = "G:"
elif platform.system() == "Linux":
    sd_path = "/media/timdrake/8GB SD2/"
else:
    raise Exception("Unsupported OS")

# Get list of files only (ignore folders)
#files_only = [f for f in os.listdir(sd_path) if os.path.isfile(os.path.join(sd_path, f))]
## Optional: sort by last modified time (newest last)
#files_only.sort(key=lambda f: os.path.getmtime(os.path.join(sd_path, f)))
## Choose the most recent file (or second most recent if needed)
#recent_file = files_only[-1]  # Use [-2] if you have a reason to skip the newest
#
#full_path = os.path.join(sd_path, recent_file)
#df = pd.read_csv(full_path)
#df = pd.read_csv("G:data12.csv")
#df = pd.read_csv("/media/timdrake/8GB SD2/data12.csv")
dpg.create_context()

with dpg.font_registry():
    small = dpg.add_font("Assets/RobotoMono-Regular.ttf", 14)
    default = dpg.add_font("Assets/RobotoMono-Regular.ttf", 18)
    medium = dpg.add_font("Assets/RobotoMono-Regular.ttf", 25)
    large = dpg.add_font("Assets/RobotoMono-Regular.ttf", 30)
    xl = dpg.add_font("Assets/RobotoMono-Regular.ttf", 40)
    
dpg.bind_font(default)

class Stats:   
    def __init__(self):
        pass
        #self.op_time = time_list
        #
        #
        #self.max_thrust = 0
        #self.max_pressure = 0
        #self.max_tank_pressure = 0
        #self.test_time = 0
        #
        #self.fill_range = self.get_range(fill, 10, 11)
        #self.fill_time = time_list[self.get_index(fill, 10, 11)[1]]-time_list[self.get_index(fill, 10, 11)[0]]
        #
        #self.vent_range = self.get_range(vent, 8, 9)
        #self.vent_time = time_list[self.get_index(vent, 8, 9)[1]]-time_list[self.get_index(vent, 8, 9)[0]]
        #
        #self.mov_range = self.get_range(mov, 6, 7)
        #self.mov_time = time_list[self.get_index(mov, 6, 7)[1]]-time_list[self.get_index(mov, 6, 7)[0]]
        #self.arm_range = self.get_range(arm, 4, 5)
        #self.arm_time = time_list[self.get_index(arm, 4, 5)[1]]-time_list[self.get_index(arm, 4, 5)[0]]
        #
        #self.batt_start = voltage_batt[0]
        #self.batt_end = voltage_batt[len(voltage_batt)-1]
        #
        #self.burn_time = time_list[self.get_index(mov, 6, 7)[1]] - time_list[self.get_index(mov, 6, 7)[0]]
        
    def get_range(self,event,min,max):
        start,stop = self.get_index(event,min,max)
        return [time_list[start:stop], [0.0] * len(time_list[start:stop]), [14.0] * len(time_list[start:stop]), [self.max_pressure] * len(time_list[start:stop]), [self.max_thrust] * len(time_list[start:stop]), [10.0] * len(time_list[start:stop])]

    def get_index(self,event,min,max):
        a = 0
        start = 0
        stop = 0
        for index, i in enumerate(event):
            if i == max and a == 0:
                a = 1
                start = index
            if i == min and a == 1:
                a = 2
                stop = index
        return start, stop   
         
def get_burn_end(input_list, burn_begin):
    for i, j in enumerate(input_list):
        if i >= burn_begin + 5:
            if j < 10:
                return i        
                    
def to_minutes(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    
    return "%02d:%02d" % (minutes, seconds)
        
def toggle_plot_visibility(sender, app_data):
    """Callback function to toggle the plot's visibility."""
    # Toggle the plot's visibility using configure_item
    if app_data == 537:
        dpg.configure_item("pressure_plot", show= True)
        dpg.configure_item("discrete_plot", show= False)
        dpg.configure_item("load_cell_plot", show= False)
        dpg.configure_item("voltage_plot", show= False)
    if app_data == 538:
        dpg.configure_item("pressure_plot", show= False)
        dpg.configure_item("discrete_plot", show= True)
        dpg.configure_item("load_cell_plot", show= False)
        dpg.configure_item("voltage_plot", show= False)
    if app_data == 539:
        dpg.configure_item("pressure_plot", show= False)
        dpg.configure_item("discrete_plot", show= False)
        dpg.configure_item("load_cell_plot", show= True)
        dpg.configure_item("voltage_plot", show= False)
    if app_data == 540:
        dpg.configure_item("pressure_plot", show= False)
        dpg.configure_item("discrete_plot", show= False)
        dpg.configure_item("load_cell_plot", show= False)
        dpg.configure_item("voltage_plot", show= True)
    
    # Show/hide shaded regions for events      
    if app_data == 546: 
        dpg.configure_item("arm_shade_p", show= not dpg.is_item_shown("arm_shade_p"))
        dpg.configure_item("arm_shade_d", show= not dpg.is_item_shown("arm_shade_d"))
        dpg.configure_item("arm_shade_t", show= not dpg.is_item_shown("arm_shade_t"))
        dpg.configure_item("arm_shade_v", show= not dpg.is_item_shown("arm_shade_v"))
        
        
    if app_data == 561: 
        dpg.configure_item("fill_shade_p", show= not dpg.is_item_shown("fill_shade_p"))
        dpg.configure_item("fill_shade_d", show= not dpg.is_item_shown("fill_shade_d"))
        dpg.configure_item("fill_shade_t", show= not dpg.is_item_shown("fill_shade_t"))
        dpg.configure_item("fill_shade_v", show= not dpg.is_item_shown("fill_shade_v"))
        
    if app_data == 567: 
        dpg.configure_item("vent_shade_p", show= not dpg.is_item_shown("vent_shade_p"))
        dpg.configure_item("vent_shade_d", show= not dpg.is_item_shown("vent_shade_d"))
        dpg.configure_item("vent_shade_t", show= not dpg.is_item_shown("vent_shade_t"))
        dpg.configure_item("vent_shade_v", show= not dpg.is_item_shown("vent_shade_v"))
        
    if app_data == 558: 
        dpg.configure_item("mov_shade_p", show= not dpg.is_item_shown("mov_shade_p"))
        dpg.configure_item("mov_shade_d", show= not dpg.is_item_shown("mov_shade_d"))
        dpg.configure_item("mov_shade_t", show= not dpg.is_item_shown("mov_shade_t"))
        dpg.configure_item("mov_shade_v", show= not dpg.is_item_shown("mov_shade_v"))
        
    if app_data == 557: 
        dpg.set_axis_limits("x_axis_p", time_list[stats.get_index(arm, 4, 5)[0]], time_list[stats.get_index(arm, 4, 5)[1]])
        dpg.set_axis_limits("x_axis_d", time_list[stats.get_index(arm, 4, 5)[0]], time_list[stats.get_index(arm, 4, 5)[1]])
        dpg.set_axis_limits("x_axis_t", time_list[stats.get_index(arm, 4, 5)[0]], time_list[stats.get_index(arm, 4, 5)[1]])
        dpg.set_axis_limits("x_axis_v", time_list[stats.get_index(arm, 4, 5)[0]], time_list[stats.get_index(arm, 4, 5)[1]])
        
    if app_data == 556: 
        dpg.set_axis_limits("x_axis_p", 0, time_list[len(time_list)-1])
        dpg.set_axis_limits("x_axis_d", 0, time_list[len(time_list)-1])
        dpg.set_axis_limits("x_axis_t", 0, time_list[len(time_list)-1])
        dpg.set_axis_limits("x_axis_v", 0, time_list[len(time_list)-1])
        
#df["Time[ms]"] = round(df['Time[ms]'].multiply(0.001),1)
time_list = 0
pt1 = 0
pt2 = 0
pt3 = 0
pt4 = 0
pt5 = 0
pt6 = 0

c1 = 0
c2 = 0
fill = 0
vent = 0
mov = 0
arm = 0
py1 = 0
py2 = 0

load_cell = 0

voltage_batt = 0
voltage_5v = 0
voltage_radio = 0

stats = Stats()

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

viewport_dim = [1920, 1280]  
WINDOW_DIM = [250, viewport_dim[1]]
PLOT_WINDOW_DIM = [viewport_dim[0]-WINDOW_DIM[0], viewport_dim[1]]

EVENTS_WINDOW_SIZE = (450, 470)
EVENTS_WINDOW_POS = (PLOT_WINDOW_DIM[0]-EVENTS_WINDOW_SIZE[0]-x_offset, 0+y_offset)

STATUS_BAR_POS = (0, 0)
STATUS_BAR_SIZE = (WINDOW_DIM[0] - 25, 60)

dpg.create_viewport(title='Custom Title', 
                    width=viewport_dim[0], 
                    height=viewport_dim[1],
                    min_width = viewport_dim[0], 
                    #max_width = 1280,
                    min_height = viewport_dim[1], 
                    #max_height = 720,
                    )

with dpg.window(label="Plots",
                no_title_bar = True,
                width=PLOT_WINDOW_DIM[0], 
                height=PLOT_WINDOW_DIM[1],
                pos = [WINDOW_DIM[0],0]):
    
    
    with dpg.child_window(width=settings.STATUS_BAR_SIZE[0], height=settings.STATUS_BAR_SIZE[1], no_scrollbar=True):
        with dpg.group(horizontal=True):
            # Computer time
            #txt_comp_time = dpg.add_text(" ", tag="comp_time")
            #dpg.bind_item_font(txt_comp_time, large)
            
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

    
    with dpg.theme() as alpha_theme:
        with dpg.theme_component(0):
            dpg.add_theme_style(dpg.mvPlotStyleVar_FillAlpha, .25, category=dpg.mvThemeCat_Plots)
            
    # Pressure plot        
    with dpg.plot(label="Pressure Transducers", height=PLOT_WINDOW_DIM[1], width=PLOT_WINDOW_DIM[0]-30, tag="pressure_plot"):
        dpg.add_plot_legend()
        with dpg.plot_axis(dpg.mvXAxis, label="Timestamp", tag="x_axis_busIMUaccel"):
            pass
        with dpg.plot_axis(dpg.mvYAxis, label="m/s^2"):
            dpg.set_axis_limits(dpg.last_item(), -20, 20) 
            dpg.add_line_series([], [], label="PHIL", tag="phil_pressure")

        # lines
        #dpg.add_line_series(stats.op_time, pt1, label="PHIL", parent="y_axis_p")
        #dpg.add_line_series(stats.op_time, pt2, label="INJECTOR", parent="y_axis_p")
        #dpg.add_line_series(stats.op_time, pt3, label="COMBUSTION CHAMBER", parent="y_axis_p")
        #dpg.add_line_series(stats.op_time, pt4, label="TANK", parent="y_axis_p")
      
                    
    dpg.bind_font(default)
 
    with dpg.window(label="Stats",
                    no_title_bar = True,
                    width=WINDOW_DIM[0], 
                    height=WINDOW_DIM[1],
                    pos = [0,0]):
        
        with dpg.child_window(width=WINDOW_DIM[0]-20, height=WINDOW_DIM[1]-20, menubar=False):
            #dpg.add_separator(label="This is a separator with text")
            h1 = dpg.add_text("Burn Time")
            d1 = dpg.add_text(f"{round(0,2)} sec")
            
            dpg.add_separator()
            h2 = dpg.add_text(f"Max Thrust")  
            d2 = dpg.add_text(f"{round(0,2)} lbf")
            
            dpg.add_separator(label="Pressure") 
            dpg.add_text(f"Max:  {0} PSI")
            dpg.add_text(f"Tank: {0} PSI")
            dpg.add_text(f"Fill Time: {to_minutes(0)}") 
            dpg.add_text(f"Test Time: {to_minutes(0)}") 
            
            dpg.add_separator(label="Battery") 
            dpg.add_text(f"Start Volts: {0}V") 
            dpg.add_text(f"End Volts  : {0}V")
        
        
        
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
            btn = dpg.add_button(label="    ", parent=row_id)
            dpg.bind_item_theme(btn, theme_tag)

            # Event text
            txt_event = dpg.add_text(theme_tag, parent=row_id)
            dpg.bind_item_font(txt_event, large)

            # Time text
            txt_time = dpg.add_text(f"000.00s", parent=row_id)
            dpg.bind_item_font(txt_time, large)
        
        
# Register the key press handler
with dpg.handler_registry():
    dpg.add_key_press_handler(callback=toggle_plot_visibility)
    dpg.add_key_press_handler(dpg.mvKey_F, callback=lambda:dpg.toggle_viewport_fullscreen())
    


dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()