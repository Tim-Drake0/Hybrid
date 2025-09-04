import dearpygui.dearpygui as dpg
import pandas as pd
from math import sin
import csv


df = pd.read_csv("E:data12.csv")
dpg.create_context()


df["Time[ms]"] = round(df['Time[ms]'].multiply(0.001),1)
time_list = df["Time[ms]"].to_list()
pt1 = df['PT1[psi]'].to_list()
pt2 = df['PT2[psi]'].to_list()
pt3 = df['PT3[psi]'].to_list()
pt4 = df['PT4[psi]'].to_list()
pt5 = df['PT5[psi]'].to_list()
pt6 = df['PT6[psi]'].to_list()

op_time = time_list[100:1425]
# Pressure Transducer Plot
#fig, pressures = plt.subplots(figsize = (20,5)) #figsize = (40,10)
#pressures.plot(df['Time[ms]'], df['PT1[psi]'], label = 'PHIL')
#pressures.plot(df['Time[ms]'], df['PT2[psi]'], label = 'OX INJECTOR')
#pressures.plot(df['Time[ms]'], df['PT3[psi]'], label = 'COMBUSTION CHAMBER')
#pressures.plot(df['Time[ms]'], df['PT4[psi]'], label = 'TANK')
#pressures.plot(df['Time[ms]'], df['PT5[psi]'], label = 'PT5')
#pressures.plot(df['Time[ms]'], df['PT6[psi]'], label = 'PT6')
#
#pressures.legend()
#pressures.set_xlabel('Time [sec]')
#pressures.set_ylabel('PSI')
#pressures.set_title('Pressure')
#pressures.grid()
    
    
    
dpg.create_viewport(title='Custom Title', 
                    width=1280, 
                    height=720,
                    min_width = 1280,
                    max_width = 1280,
                    min_height = 720,
                    max_height = 720,
                    )

with dpg.window(label="Example Window",
                no_title_bar = True,
                width=1280, 
                height=400,
                pos = [0,300]):

    with dpg.plot(label="Line Series", height=370, width=1250):
        dpg.add_plot_legend()

        # REQUIRED: create x and y axes
        dpg.add_plot_axis(dpg.mvXAxis, label="Time [sec]")
        dpg.add_plot_axis(dpg.mvYAxis, label="Pressure [PSI]", tag="y_axis")

        # series belong to a y axis
        dpg.add_line_series(op_time, pt1, label="PHIL", parent="y_axis")
        dpg.add_line_series(op_time, pt2, label="INJECTOR", parent="y_axis")
        dpg.add_line_series(op_time, pt3, label="COMBUSTION CHAMBER", parent="y_axis")
        dpg.add_line_series(op_time, pt4, label="TANK", parent="y_axis")
        #dpg.add_line_series(op_time, pt5, label="PT5", parent="y_axis")
        #dpg.add_line_series(op_time, pt6, label="PT6", parent="y_axis")


dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()