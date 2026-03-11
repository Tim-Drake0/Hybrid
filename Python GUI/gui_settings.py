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

LED_W = 140
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

EVENTS_WINDOW_SIZE = (350,550)
EVENTS_WINDOW_POS = (WINDOW_DIM[0] - EVENTS_WINDOW_SIZE[0], STATUS_BAR_SIZE[1] + 10)

INFO_WINDOW_POS = (0, STATUS_BAR_SIZE[1] + 10)
INFO_WINDOW_SIZE = (WINDOW_DIM[0] - EVENTS_WINDOW_SIZE[0] - 1000, 550)  

ERROR_WINDOW_POS = (0, INFO_WINDOW_POS[1] + INFO_WINDOW_SIZE[1])
ERROR_WINDOW_SIZE = (INFO_WINDOW_SIZE[0], WINDOW_DIM[0]-INFO_WINDOW_SIZE[1])  

PRESS_PLOT_WINDOW_SIZE = (EVENTS_WINDOW_POS[0] - INFO_WINDOW_SIZE[0] + 5, 550) 
PRESS_PLOT_WINDOW_POS = (INFO_WINDOW_SIZE[0] + 5, STATUS_BAR_SIZE[1] + 10)

PLOT_WINDOW_POS = (PRESS_PLOT_WINDOW_POS[0], STATUS_BAR_SIZE[1] + 565)
PLOT_WINDOW_SIZE = (WINDOW_DIM[0]- PRESS_PLOT_WINDOW_POS[0] - 5, 770)  

RIGHT_WINDOWS = [
    "right_window_bus_info",
    "right_window_bme280",
    "right_window_lsm9ds1",
    "right_window_adxl375",
    "right_window_eeprom"
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
    
