import dearpygui.dearpygui as dpg
import pandas as pd
from math import sin
import csv
    
df = pd.read_csv("data12.csv")
dpg.create_context()
#dpg.toggle_viewport_fullscreen()
    
    
def toggle_plot_visibility(sender, app_data):
    """Callback function to toggle the plot's visibility."""
    # Toggle the plot's visibility using configure_item
    if app_data == 537:
        dpg.configure_item("pressure_plot", show= True)
        dpg.configure_item("discrete_plot", show= False)
        dpg.configure_item("load_cell_plot", show= False)
    if app_data == 538:
        dpg.configure_item("pressure_plot", show= False)
        dpg.configure_item("discrete_plot", show= True)
        dpg.configure_item("load_cell_plot", show= False)
    if app_data == 539:
        dpg.configure_item("pressure_plot", show= False)
        dpg.configure_item("discrete_plot", show= False)
        dpg.configure_item("load_cell_plot", show= True)
        
    
    
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

op_time = time_list[100:1425]
   
 
thrust = df['LC[lbf]'].to_list()
max_thrust = max(thrust)


viewport_dim = [1280, 720]    
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
                width=1080, 
                height=700,
                pos = [200,0]):

    window_dim = [1050, 640]
    plot_dim = [1050, 620]
    #with dpg.menu_bar():
        # Pressure plot
        #with dpg.menu(label="Pressure", show = True):
        #    with dpg.child_window(height=window_dim[1], width=window_dim[0], show = True, tag="my_plot"):
    with dpg.plot(label="Pressure Transducers", height=plot_dim[1], width=plot_dim[0], tag="pressure_plot"):
        dpg.add_plot_legend()
        # REQUIRED: create x and y axes
        dpg.add_plot_axis(dpg.mvXAxis, label="Time [sec]")
        dpg.add_plot_axis(dpg.mvYAxis, label="Pressure [PSI]", tag="y_axis_p")

        # lines
        dpg.add_line_series(op_time, pt1, label="PHIL", parent="y_axis_p")
        dpg.add_line_series(op_time, pt2, label="INJECTOR", parent="y_axis_p")
        dpg.add_line_series(op_time, pt3, label="COMBUSTION CHAMBER", parent="y_axis_p")
        dpg.add_line_series(op_time, pt4, label="TANK", parent="y_axis_p")
        #dpg.add_line_series(op_time, pt5, label="PT5", parent="y_axis_p")
        #dpg.add_line_series(op_time, pt6, label="PT6", parent="y_axis_p")
                    
        # Discretes Plot
        #with dpg.menu(label="Discretes"):
        #    with dpg.child_window(height=window_dim[1], width=window_dim[0]):
    with dpg.plot(label="Discrete Logic", height=plot_dim[1], width=plot_dim[0], tag = "discrete_plot"):
        dpg.add_plot_legend()
        # REQUIRED: create x and y axes
        dpg.add_plot_axis(dpg.mvXAxis, label="Time [sec]")
        dpg.add_plot_axis(dpg.mvYAxis, label="Pressure [PSI]", tag="y_axis")
        #dpg.set_axis_limits(dpg.mvYAxis, 0, 16)

        # lines
        dpg.add_line_series(op_time, c1, label="CONTINUITY 1", parent="y_axis")
        dpg.add_line_series(op_time, c2, label="CONTINUITY 2", parent="y_axis")
        dpg.add_line_series(op_time, fill, label="FILL", parent="y_axis")
        dpg.add_line_series(op_time, vent, label="VENT", parent="y_axis")
        dpg.add_line_series(op_time, mov, label="MOV", parent="y_axis")
        dpg.add_line_series(op_time, arm, label="ARM", parent="y_axis")
        dpg.add_line_series(op_time, py1, label="PY1", parent="y_axis")
        dpg.add_line_series(op_time, py2, label="PY2", parent="y_axis")
                    
        # Load Cell Plot
        #with dpg.menu(label="Load Cell"):
        #    with dpg.child_window(height=window_dim[1], width=window_dim[0]):
    with dpg.plot(label="Load Cell Thrust", height=plot_dim[1], width=plot_dim[0], tag = "load_cell_plot"):
        dpg.add_plot_legend()
        # REQUIRED: create x and y axes
        dpg.add_plot_axis(dpg.mvXAxis, label="Time [sec]")
        dpg.add_plot_axis(dpg.mvYAxis, label="Thrust [Lbf]", tag="y_axis_t")
        #dpg.set_axis_limits(dpg.mvYAxis, 0, 16)

        # lines
        dpg.add_line_series(op_time, load_cell, label="Load Cell", parent="y_axis_t")

with dpg.window(label="Stats",
                no_title_bar = True,
                width=200, 
                height=700,
                pos = [0,0]):
    with dpg.table(header_row=False):

        # use add_table_column to add columns to the table,
        # table columns use slot 0
        dpg.add_table_column()
        dpg.add_table_column()

        # add_table_next_column will jump to the next row
        # once it reaches the end of the columns
        # table next column use slot 1
        with dpg.table_row():

            dpg.add_text("Burn Time")
            dpg.add_text(str(5)+" sec")
            
        with dpg.table_row():
            
            dpg.add_text("Max Thrust")
            dpg.add_text(str(max_thrust)+" lbf")
            
# Register the key press handler
with dpg.handler_registry():
    # Bind the 'P' key (mvKey_P) to the callback function
    dpg.add_key_press_handler(callback=toggle_plot_visibility)
            


dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()