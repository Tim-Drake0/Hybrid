import dearpygui.dearpygui as dpg
import serial_reader as sr
import serial_writer as sw
import time
import struct
import sys
from pathlib import Path
sensor_path = Path(__file__).parent.parent
sys.path.append(str(sensor_path))
import gui_settings as settings

CMD_GET_EEPROM_SETTINGS     = 0x04
CMD_EDIT_EEPROM_SETTINGS    = 0x05

repo_root = Path(__file__).resolve().parents[2]  # adjust n once
CONFIG_DEFAULTS_FILE = repo_root / "config.txt"

class EEPROMConfig:
    baroSensor: int = 0
    temp_sample_rate:  int = 0
    press_sample_rate:  int = 0
    hum_sample_rate:  int = 0
    testMode:  int = 0
    printSerial:  int = 0
    recordData:  int = 0
    SD_sample_rate:  int = 0
    max_flight_dirs:  int = 0
    telemSendRate:  int = 0
    
config = EEPROMConfig()

def on_select(sender, app_data):
    dpg.set_value(sender, False)
    if app_data:
        settings.show_right_window("right_window_eeprom")

def send_get_eeprom_settings() -> bool:
    """Request packet containing current EEPROM settings."""
    return sw._send(CMD_GET_EEPROM_SETTINGS)

def send_edit_eeprom_settings() -> bool:
    """Send packet containing new EEPROM settings."""
    
    baroSensor = struct.pack("B", config.baroSensor) 
    temp_sample_rate = struct.pack("B", config.temp_sample_rate) 
    press_sample_rate = struct.pack("B", config.press_sample_rate) 
    hum_sample_rate = struct.pack("B", config.hum_sample_rate) 
    testMode = struct.pack("B", config.testMode) 
    printSerial = struct.pack("B", config.printSerial) 
    recordData = struct.pack("B", config.recordData) 
    SD_sample_rate = struct.pack("<H", config.SD_sample_rate) 
    max_flight_dirs = struct.pack("<H", config.max_flight_dirs) 
    telemSendRate = struct.pack("<H", config.telemSendRate) 
    
    body = baroSensor + temp_sample_rate + press_sample_rate + hum_sample_rate + testMode + printSerial + recordData + SD_sample_rate + max_flight_dirs + telemSendRate
    return sw._send(CMD_EDIT_EEPROM_SETTINGS, body)

def make_int_input(tag, attr):
    def cb(s, a):
        if a.isdigit():
            setattr(config, attr, int(a))
        else:
            dpg.set_value(s, str(getattr(config, attr)))
    return cb

def get_config():
    print("Getting EEPROM config")
    send_get_eeprom_settings()
    
    time.sleep(.5)
    
    dpg.set_value("eeprom_baroSensor", f"{config.baroSensor}")
    dpg.set_value("eeprom_temp_sample_rate", f"{config.temp_sample_rate}")
    dpg.set_value("eeprom_press_sample_rate", f"{config.press_sample_rate}")
    dpg.set_value("eeprom_hum_sample_rate", f"{config.hum_sample_rate}")
    dpg.set_value("eeprom_testMode", f"{config.testMode}")
    dpg.set_value("eeprom_printSerial", f"{config.printSerial}")
    dpg.set_value("eeprom_recordData", f"{config.recordData}")
    dpg.set_value("eeprom_SD_sample_rate", f"{config.SD_sample_rate}")
    dpg.set_value("eeprom_max_flight_dirs", f"{config.max_flight_dirs}")
    dpg.set_value("eeprom_telemSendRate", f"{config.telemSendRate}")

def reset2defaults():
    # Load default config
    with open(CONFIG_DEFAULTS_FILE, "r") as f:
        for line in f:
            key, value = line.strip().split("=")
            dpg.set_value(f"eeprom_{key}", f"{int(value)}")
    
    
def readSettings(payload):
    config.baroSensor = payload[0]
    config.temp_sample_rate = payload[1]
    config.press_sample_rate = payload[2]
    config.hum_sample_rate = payload[3]
    config.testMode = payload[4]
    config.printSerial = payload[5]
    config.recordData = payload[6]
    config.SD_sample_rate = (payload[8] << 8) | payload[7]
    config.max_flight_dirs = (payload[10] << 8) | payload[9]
    config.telemSendRate = (payload[12] << 8) | payload[11]
  
def init_window():
    # EEPROM window
    with dpg.child_window(width=settings.RIGHT_WINDOW_SIZE[0], height=settings.RIGHT_WINDOW_SIZE[1], pos=settings.RIGHT_WINDOW_POS, tag="right_window_eeprom", show=True): 
                
        txt_eeprom_window = dpg.add_text("EEPROM Settings") 
        dpg.bind_item_font(txt_eeprom_window, settings.large) 
        
        dpg.add_button(label="Reset to defaults", callback=reset2defaults) 
        
        with dpg.group(horizontal=True):
            dpg.add_button(label="Get config from hardware", callback=get_config) 
            dpg.add_button(label="Update configuration", callback=send_edit_eeprom_settings) 
        
        dpg.add_spacer(height=8)
        
        with dpg.table(width=300,
                       header_row=True, resizable=True, delay_search=True,
                       borders_outerH=True, borders_innerV=True, 
                       borders_outerV=True, row_background=False) as table_id:
            dpg.add_table_column(label="Setting")
            dpg.add_table_column(label="Val", init_width_or_weight=75, width_fixed=True)

            with dpg.table_row():
                dpg.add_text("baroSensor")
                dpg.add_input_text(width=75, default_value=f"{config.baroSensor}", tag="eeprom_baroSensor",callback=make_int_input("eeprom_baroSensor", "baroSensor"))
            
            with dpg.table_row():
                dpg.add_text("temp_sample_rate")
                dpg.add_input_text(width=75, default_value=f"{config.temp_sample_rate}", tag="eeprom_temp_sample_rate",callback=make_int_input("eeprom_temp_sample_rate", "temp_sample_rate"))
                
            with dpg.table_row():
                dpg.add_text("press_sample_rate")
                dpg.add_input_text(width=75, default_value=f"{config.press_sample_rate}", tag="eeprom_press_sample_rate",callback=make_int_input("eeprom_press_sample_rate", "press_sample_rate"))

            with dpg.table_row():
                dpg.add_text("hum_sample_rate")
                dpg.add_input_text(width=75, default_value=f"{config.hum_sample_rate}", tag="eeprom_hum_sample_rate",callback=make_int_input("eeprom_hum_sample_rate", "hum_sample_rate"))

            with dpg.table_row():
                dpg.add_text("testMode")
                dpg.add_input_text(width=75, default_value=f"{config.testMode}", tag="eeprom_testMode",callback=make_int_input("eeprom_testMode", "testMode"))

            with dpg.table_row():
                dpg.add_text("printSerial")
                dpg.add_input_text(width=75, default_value=f"{config.printSerial}", tag="eeprom_printSerial",callback=make_int_input("eeprom_printSerial", "printSerial"))

            with dpg.table_row():
                dpg.add_text("recordData")
                dpg.add_input_text(width=75, default_value=f"{config.recordData}", tag="eeprom_recordData",callback=make_int_input("eeprom_recordData", "recordData"))

            with dpg.table_row():
                dpg.add_text("SD_sample_rate")
                dpg.add_input_text(width=75, default_value=f"{config.SD_sample_rate}", tag="eeprom_SD_sample_rate",callback=make_int_input("eeprom_SD_sample_rate", "SD_sample_rate"))

            with dpg.table_row():
                dpg.add_text("max_flight_dirs")
                dpg.add_input_text(width=75, default_value=f"{config.max_flight_dirs}", tag="eeprom_max_flight_dirs",callback=make_int_input("eeprom_max_flight_dirs", "max_flight_dirs"))

            with dpg.table_row():
                dpg.add_text("telemSendRate")
                dpg.add_input_text(width=75, default_value=f"{config.telemSendRate}", tag="eeprom_telemSendRate",callback=make_int_input("eeprom_telemSendRate", "telemSendRate"))

        