import dearpygui.dearpygui as dpg

WINDOW_POS = (0,0)
WINDOW_DIM = (1720,1000)

TAB_WINDOW_POS = (0,0)
TAB_WINDOW_DIM = (WINDOW_DIM[0],WINDOW_DIM[1]-TAB_WINDOW_POS[1])

# Child window size and positions:
STATUS_BAR_POS = (0, 0)
STATUS_BAR_SIZE = (WINDOW_DIM[0] - 25, 60)



y_offset = 32
x_offset = 5

LED_W = 120
LED_H = 100
LED_SPACING_X = 10
LED_SPACING_Y = 10
LED_COLS = 2

led_panel_states = {
    "FILL":   {"state": 0, "color_on": (0, 200, 255),   "color_off": (0, 40, 60),  "label_on": "OPEN",   "label_off": "CLOSED"},
    "VENT":   {"state": 0, "color_on": (0, 200, 255),   "color_off": (0, 40, 60),  "label_on": "OPEN",   "label_off": "CLOSED"},
    "MOV":    {"state": 0, "color_on": (0, 200, 255),   "color_off": (0, 40, 60),  "label_on": "OPEN",   "label_off": "CLOSED"},
    "ARM":    {"state": 0, "color_on": (255, 120, 0),   "color_off": (60, 25, 0),  "label_on": "ARMED",  "label_off": "SAFE"},
    "PY1":    {"state": 0, "color_on": (255, 50, 50),   "color_off": (60, 10, 10), "label_on": "FIRE",   "label_off": "SAFE"},
    "PY2":    {"state": 0, "color_on": (255, 50, 50),   "color_off": (60, 10, 10), "label_on": "FIRE",   "label_off": "SAFE"},
    "C1":     {"state": 0, "color_on": (50, 255, 100),  "color_off": (10, 60, 20), "label_on": "CONT",   "label_off": "NO CONT"},
    "C2":     {"state": 0, "color_on": (50, 255, 100),  "color_off": (10, 60, 20), "label_on": "CONT",   "label_off": "NO CONT"},
}

EVENTS_WINDOW_SIZE = (300,550)
EVENTS_WINDOW_POS = (WINDOW_DIM[0] - EVENTS_WINDOW_SIZE[0], STATUS_BAR_SIZE[1] + 10)

INFO_WINDOW_POS = (0, STATUS_BAR_SIZE[1] + 10)
INFO_WINDOW_SIZE = (570, 550)  

ERROR_WINDOW_POS = (0, INFO_WINDOW_POS[1] + INFO_WINDOW_SIZE[1])
ERROR_WINDOW_SIZE = (INFO_WINDOW_SIZE[0], WINDOW_DIM[1]-INFO_WINDOW_SIZE[1]-485)  

PRESS_PLOT_WINDOW_SIZE = (EVENTS_WINDOW_POS[0] - INFO_WINDOW_SIZE[0] + 5, 550) 
PRESS_PLOT_WINDOW_POS = (INFO_WINDOW_SIZE[0] + 5, STATUS_BAR_SIZE[1] + 10)

PLOT_WINDOW_POS = (PRESS_PLOT_WINDOW_POS[0], STATUS_BAR_SIZE[1] + 565)
PLOT_WINDOW_SIZE = (WINDOW_DIM[0]- PRESS_PLOT_WINDOW_POS[0] - 5, ERROR_WINDOW_SIZE[1])  

RIGHT_WINDOWS = [
    "right_window_bus_info",
    "right_window_bme280",
    "right_window_lsm9ds1",
    "right_window_adxl375",
    "right_window_eeprom"
]

# At the top of your file or in an init function, parse the saturation data:
SAT_TEMPS = [
    0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,
    21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,
    41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,
    61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,
    81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97
]
SAT_PRESSURES = [
    278.33,282.88,287.49,292.15,296.87,301.64,306.46,311.35,316.29,321.28,326.34,
    331.45,336.62,341.84,347.13,352.47,357.88,363.34,368.87,374.45,380.10,
    385.81,391.58,397.42,403.32,409.28,415.30,421.39,427.54,433.76,440.05,
    446.40,452.82,459.30,465.86,472.48,479.17,485.93,492.76,499.66,506.62,
    513.65,520.75,527.92,535.16,542.47,549.85,557.30,564.82,572.41,580.08,
    587.82,595.63,603.52,611.48,619.51,627.96,636.45,644.79,653.21,661.71,
    670.30,678.97,687.72,696.56,705.49,714.51,723.61,732.80,742.09,751.46,
    760.93,770.49,780.14,789.89,799.74,809.68,819.72,829.87,840.11,850.46,
    860.92,871.48,882.15,892.93,903.82,914.83,925.96,937.21,948.58,960.08,
    971.72,983.49,995.41,1007.5,1019.7,1032.1,1044.8
]

def show_right_window(tag):
    for window in RIGHT_WINDOWS:
        dpg.hide_item(window)
    dpg.show_item(tag)
    
def createFonts():
    global small, default, medium, large, xl
    with dpg.font_registry():
        small = dpg.add_font("Assets/RobotoMono-Regular.ttf", 14)
        default = dpg.add_font("Assets/RobotoMono-Regular.ttf", 18)
        medium = dpg.add_font("Assets/RobotoMono-Regular.ttf", 25)
        large = dpg.add_font("Assets/RobotoMono-Regular.ttf", 30)
        xl = dpg.add_font("Assets/RobotoMono-Regular.ttf", 40)
    
