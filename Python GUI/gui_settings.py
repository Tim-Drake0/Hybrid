import dearpygui.dearpygui as dpg

WINDOW_POS = (0,0)
WINDOW_DIM = (1920,1080)

TAB_WINDOW_POS = (0,0)
TAB_WINDOW_DIM = (WINDOW_DIM[0],WINDOW_DIM[1]-TAB_WINDOW_POS[1])

# Child window size and positions:
STATUS_BAR_POS = (0, 0)
STATUS_BAR_SIZE = (WINDOW_DIM[0] - 25, 60)

INFO_WINDOW_POS = (0, STATUS_BAR_SIZE[1] + 10)
INFO_WINDOW_SIZE = (WINDOW_DIM[0] - 25, 770)  

PLOT_WINDOW_POS = (0, STATUS_BAR_SIZE[1] + 800)
PLOT_WINDOW_SIZE = (WINDOW_DIM[0] - 25, 770)  

y_offset = 32
x_offset = 5

EVENTS_WINDOW_SIZE = (450, 470)
EVENTS_WINDOW_POS = (WINDOW_DIM[0]-EVENTS_WINDOW_SIZE[0]-x_offset, 0+y_offset)

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
    
