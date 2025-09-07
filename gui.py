import dearpygui.dearpygui as dpg
import pandas as pd
from math import sin
import csv
    
df = pd.read_csv("data12.csv")
dpg.create_context()

with dpg.font_registry():     
    default_font = dpg.add_font("Assets/RobotoMono-Regular.ttf", 25)
    header_font = dpg.add_font("Assets/RobotoMono-Regular.ttf", 35)
    data_font = dpg.add_font("Assets/RobotoMono-Regular.ttf", 30)
    small_font = dpg.add_font("Assets/RobotoMono-Regular.ttf", 20)

class Stats:
    def __init__(self):
        self.op_time = time_list#[100:1425]
        self.burn_time = 5.34
        self.max_thrust = max(load_cell)
        self.max_pressure = max(pt1+pt2+pt3+pt4+pt5+pt6)
        self.max_tank_pressure = max(pt4)
        
        self.fill_range = self.get_range(fill, 10, 11)
        self.fill_time = self.get_index(fill, 10, 11)[0]-self.get_index(fill, 10, 11)[1]
        
        self.vent_range = self.get_range(vent, 8, 9)
        self.vent_time = self.get_index(vent, 8, 9)[0]-self.get_index(vent, 8, 9)[1]
        
        self.mov_range = self.get_range(mov, 6, 7)
        self.mov_time = self.get_index(mov, 6, 7)[0]-self.get_index(mov, 6, 7)[1]
        
        self.arm_range = self.get_range(arm, 4, 5)
        self.arm_time = self.get_index(arm, 4, 5)[0]-self.get_index(arm, 4, 5)[1]
        #[0 time, 1 zeros, 2 discrete, 3 pressure, 4 load cell, 5 battery voltage]
        
        self.batt_start = voltage_batt[0]
        self.batt_end = voltage_batt[len(voltage_batt)-1]

    def get_range(self,event,min,max):
        start,stop = self.get_index(event,min,max)
        print(self.get_index(event,min,max)[0])
        return [self.op_time[start:stop], [0.0] * len(self.op_time[start:stop]), [14.0] * len(self.op_time[start:stop]), [self.max_pressure] * len(self.op_time[start:stop]), [self.max_thrust] * len(self.op_time[start:stop]), [10.0] * len(self.op_time[start:stop])]

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
        
df["Time[ms]"] = round(df['Time[ms]'].multiply(0.001),1)
time_list = df["Time[ms]"].to_list()
pt1 = df['PT1[psi]'].to_list()
pt2 = df['PT2[psi]'].to_list()
pt3 = df['PT3[psi]'].to_list()
pt4 = df['PT4[psi]'].to_list()
pt5 = df['PT5[psi]'].to_list()
pt6 = df['PT6[psi]'].to_list()

c1 = (df['C1'] + 14).to_list() 
c2 = (df['C2'] + 12).to_list() 
fill = (df['FILL'] + 10).to_list()
vent = (df['VENT'] + 8).to_list()
mov = (df['MOV'] + 6).to_list() 
arm = (df['ARM'] + 4).to_list() 
py1 = (df['PY1'] + 2).to_list() 
py2 = (df['PY2'] + 0).to_list() 

load_cell = df['LC[lbf]'].to_list()

voltage_batt = df['BATT[V]'].to_list()
voltage_5v = df['5V[V]'].to_list()
voltage_radio = df['RADIO[V]'].to_list()

stats = Stats()

viewport_dim = [1280, 720]  
statsWindow_dim = [250, viewport_dim[1]]
plotWindow_dim = [viewport_dim[0]-statsWindow_dim[0], viewport_dim[1]]

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
                width=plotWindow_dim[0], 
                height=plotWindow_dim[1],
                pos = [statsWindow_dim[0],0]):

    
    with dpg.theme() as alpha_theme:
        with dpg.theme_component(0):
            dpg.add_theme_style(dpg.mvPlotStyleVar_FillAlpha, .25, category=dpg.mvThemeCat_Plots)
            
    # Pressure plot        
    with dpg.plot(label="Pressure Transducers", height=plotWindow_dim[1], width=plotWindow_dim[0]-30, tag="pressure_plot"):
        dpg.add_plot_legend(horizontal = True, outside = True)
        # REQUIRED: create x and y axes
        dpg.add_plot_axis(dpg.mvXAxis, label="Time [sec]")
        with dpg.plot_axis(dpg.mvYAxis, label="Pressure [PSI]", tag="y_axis_p"):
            dpg.add_shade_series(stats.arm_range[0], stats.arm_range[1], y2=stats.arm_range[3], label="ARM", tag = "arm_shade_p", show = False)
            dpg.add_shade_series(stats.fill_range[0], stats.fill_range[1], y2=stats.fill_range[3], label="FILL", tag = "fill_shade_p", show = False)
            dpg.add_shade_series(stats.vent_range[0], stats.vent_range[1], y2=stats.vent_range[3], label="VENT", tag = "vent_shade_p", show = False)
            dpg.add_shade_series(stats.mov_range[0], stats.mov_range[1], y2=stats.mov_range[3], label="MOV", tag = "mov_shade_p", show = False)
        dpg.bind_item_theme("pressure_plot", alpha_theme)

        # lines
        dpg.add_line_series(stats.op_time, pt1, label="PHIL", parent="y_axis_p")
        dpg.add_line_series(stats.op_time, pt2, label="INJECTOR", parent="y_axis_p")
        dpg.add_line_series(stats.op_time, pt3, label="COMBUSTION CHAMBER", parent="y_axis_p")
        dpg.add_line_series(stats.op_time, pt4, label="TANK", parent="y_axis_p")
        #dpg.add_line_series(op_time, pt5, label="PT5", parent="y_axis_p")
        #dpg.add_line_series(op_time, pt6, label="PT6", parent="y_axis_p")
        
    #[0 time, 1 zeros, 2 discrete, 3 pressure, 4 load cell, 5 battery voltage]  
                  
    # Discretes Plot
    with dpg.plot(label="Discrete Logic", height=plotWindow_dim[1], width=plotWindow_dim[0]-30, tag = "discrete_plot", show = False):
        dpg.add_plot_legend(horizontal = True, outside = True)
        # REQUIRED: create x and y axes
        dpg.add_plot_axis(dpg.mvXAxis, label="Time [sec]")
        #dpg.add_plot_axis(dpg.mvYAxis, label="Logic", tag="y_axis_d")
        with dpg.plot_axis(dpg.mvYAxis, label="Logic", tag="y_axis_d"):
            dpg.add_shade_series(stats.arm_range[0], stats.arm_range[1], y2=stats.arm_range[2], label="ARM", tag = "arm_shade_d", show = False)
            dpg.add_shade_series(stats.fill_range[0], stats.fill_range[1], y2=stats.fill_range[2], label="FILL", tag = "fill_shade_d", show = False)
            dpg.add_shade_series(stats.vent_range[0], stats.vent_range[1], y2=stats.vent_range[2], label="VENT", tag = "vent_shade_d", show = False)
            dpg.add_shade_series(stats.mov_range[0], stats.mov_range[1], y2=stats.mov_range[2], label="MOV", tag = "mov_shade_d", show = False)
            
        dpg.bind_item_theme("discrete_plot", alpha_theme)
        
        # lines
        dpg.add_line_series(stats.op_time, c1, label="CONTINUITY 1", parent="y_axis_d")
        dpg.add_line_series(stats.op_time, c2, label="CONTINUITY 2", parent="y_axis_d")
        dpg.add_line_series(stats.op_time, fill, label="FILL", parent="y_axis_d")
        dpg.add_line_series(stats.op_time, vent, label="VENT", parent="y_axis_d")
        dpg.add_line_series(stats.op_time, mov, label="MOV", parent="y_axis_d")
        dpg.add_line_series(stats.op_time, arm, label="ARM", parent="y_axis_d")
        dpg.add_line_series(stats.op_time, py1, label="PY1", parent="y_axis_d")
        dpg.add_line_series(stats.op_time, py2, label="PY2", parent="y_axis_d")
                    
     # Load Cell Plot
    with dpg.plot(label="Load Cell Thrust", height=plotWindow_dim[1], width=plotWindow_dim[0]-30, tag = "load_cell_plot", show = False):
        dpg.add_plot_legend(horizontal = True, outside = True)
        # REQUIRED: create x and y axes
        dpg.add_plot_axis(dpg.mvXAxis, label="Time [sec]")
        with dpg.plot_axis(dpg.mvYAxis, label="Thrust [Lbf]", tag="y_axis_t"):
            dpg.add_shade_series(stats.arm_range[0], stats.arm_range[1], y2=stats.arm_range[4], label="ARM", tag = "arm_shade_t", show = False)
            dpg.add_shade_series(stats.fill_range[0], stats.fill_range[1], y2=stats.fill_range[4], label="FILL", tag = "fill_shade_t", show = False)
            dpg.add_shade_series(stats.vent_range[0], stats.vent_range[1], y2=stats.vent_range[4], label="VENT", tag = "vent_shade_t", show = False)
            dpg.add_shade_series(stats.mov_range[0], stats.mov_range[1], y2=stats.mov_range[4], label="MOV", tag = "mov_shade_t", show = False)
        dpg.bind_item_theme("load_cell_plot", alpha_theme)

        # lines
        dpg.add_line_series(stats.op_time, load_cell, label="Load Cell", parent="y_axis_t")
    
    # Voltage plot  
    with dpg.plot(label="Voltages", height=plotWindow_dim[1], width=plotWindow_dim[0]-30, tag="voltage_plot", show = False):
        dpg.add_plot_legend(horizontal = True, outside = True)
        # REQUIRED: create x and y axes
        dpg.add_plot_axis(dpg.mvXAxis, label="Time [sec]")
        with dpg.plot_axis(dpg.mvYAxis, label="Voltage [V]", tag="y_axis_v"):
            dpg.add_shade_series(stats.arm_range[0], stats.arm_range[1], y2=stats.arm_range[5], label="ARM", tag = "arm_shade_v", show = False)
            dpg.add_shade_series(stats.fill_range[0], stats.fill_range[1], y2=stats.fill_range[5], label="FILL", tag = "fill_shade_v", show = False)
            dpg.add_shade_series(stats.vent_range[0], stats.vent_range[1], y2=stats.vent_range[5], label="VENT", tag = "vent_shade_v", show = False)
            dpg.add_shade_series(stats.mov_range[0], stats.mov_range[1], y2=stats.mov_range[5], label="MOV", tag = "mov_shade_v", show = False)
        dpg.bind_item_theme("voltage_plot", alpha_theme)

        # lines
        dpg.add_line_series(stats.op_time, voltage_batt, label="BATT", parent="y_axis_v")
        dpg.add_line_series(stats.op_time, voltage_5v, label="5V", parent="y_axis_v")
        dpg.add_line_series(stats.op_time, voltage_radio, label="RADIO", parent="y_axis_v") 

    dpg.bind_font(default_font)


 
with dpg.window(label="Stats",
                no_title_bar = True,
                width=statsWindow_dim[0], 
                height=statsWindow_dim[1],
                pos = [0,0]):
    
    with dpg.child_window(width=statsWindow_dim[0]-20, height=statsWindow_dim[1]-20, menubar=False):
        #dpg.add_separator(label="This is a separator with text")
        h1 = dpg.add_text("Burn Time")
        d1 = dpg.add_text(f"{stats.burn_time} sec")
        
        dpg.add_separator()
        h2 = dpg.add_text(f"Max Thrust")  
        d2 = dpg.add_text(f"{stats.max_thrust} lbf")
        
        dpg.add_separator(label="Pressure") 
        dpg.add_text(f"Max:  {stats.max_pressure} PSI")
        dpg.add_text(f"Tank: {stats.max_tank_pressure} PSI")
        dpg.add_text(f"Fill Time: {to_minutes(stats.fill_time)}") 
        
        dpg.add_separator(label="Battery") 
        dpg.add_text(f"Start Volts: {stats.batt_start}V") 
        dpg.add_text(f"End Volts  : {stats.batt_end}V")
        
        dpg.add_separator(label="Hotkeys") 
        t1 = dpg.add_text(f"Change plots: 1-4")
        t2 = dpg.add_text(f"Show/hide shaded events:")
        t3 = dpg.add_text(f"A, V, P, M")
        t4 = dpg.add_text(f"Fullscreen: F")
        
        
        
        
        dpg.bind_font(default_font)        
        dpg.bind_item_font(h1,header_font)
        dpg.bind_item_font(d1,data_font)
        dpg.bind_item_font(h2,header_font)
        dpg.bind_item_font(d2,data_font)
        dpg.bind_item_font(t1,small_font)
        dpg.bind_item_font(t2,small_font)
        dpg.bind_item_font(t3,small_font)
        dpg.bind_item_font(t4,small_font)
        
        
        
        
        
# Register the key press handler
with dpg.handler_registry():
    dpg.add_key_press_handler(callback=toggle_plot_visibility)
    dpg.add_key_press_handler(dpg.mvKey_F, callback=lambda:dpg.toggle_viewport_fullscreen())
    


dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()