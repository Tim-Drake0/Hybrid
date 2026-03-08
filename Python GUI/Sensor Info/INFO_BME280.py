import dearpygui.dearpygui as dpg
import serial_reader as sr
import serial_writer as sw
import time
import sys
from pathlib import Path
sensor_path = Path(__file__).parent.parent
sys.path.append(str(sensor_path))
import gui_settings as settings

CMD_GET_BME280_SETTINGS = 0x02

oversamp_d = {
    0:"Skipped (output set to 0x80000)",
    1:"Oversampling x 1",
    2:"Oversampling x 2",
    3:"Oversampling x 4",
    4:"Oversampling x 8",
    5:"Oversampling x 16"}
mode_d = {
    0:"Sleep mode",
    1:"Forced Mode",
    2:"Forced Mode",
    3:"Normal Mode"}
t_sb_d = {
    0:"0.5",
    1:"62.5",
    2:"125",
    3:"250",
    4:"500",
    5:"1000",
    6:"10",
    7:"20"}
filter_d = {
    0:"Filter off",
    1:"2",
    2:"4",
    3:"8",
    4:"16"}
spi3w_en_d = {
    0:"3-wire",
    1:"4-wire"}

class BME280Config:
    id: int = 0x00
    oversamp_temp: str = "N/A"
    oversamp_press: str = "N/A"
    oversamp_hum: str = "N/A"
    mode: str = "N/A"
    t_sb: str = "N/A"
    filter: str = "N/A"
    spi3w_en: str = "N/A"
    
bme280_config = BME280Config()

def on_select(sender, app_data):
    dpg.set_value(sender, False)
    if app_data:
        settings.show_right_window("right_window_bme280")
        
def send_get_BME280_settings() -> bool:
    """Request packet containing current BME280 settings."""
    return sw._send(CMD_GET_BME280_SETTINGS)

def get_bme280_config():
    print("Getting bme280 config")
    send_get_BME280_settings()
    
    time.sleep(.5)
    
    dpg.set_value("bme280_id", f"{bme280_config.id}")
    dpg.set_value("bme280_oversamp_temp", f"{bme280_config.oversamp_temp}")
    dpg.set_value("bme280_oversamp_press", f"{bme280_config.oversamp_press}")
    dpg.set_value("bme280_oversamp_hum", f"{bme280_config.oversamp_hum}")
    dpg.set_value("bme280_mode", f"{bme280_config.mode}")
    dpg.set_value("bme280_t_sb", f"{bme280_config.t_sb}")
    dpg.set_value("bme280_filter", f"{bme280_config.filter}")
    dpg.set_value("bme280_spi3w_en", f"{bme280_config.spi3w_en}")
    

def readSettings(payload):
    bme280_config.id = f"{payload[0]:#04x}"
                        
    ctrl_hum = payload[1]
    ctrl_meas = payload[2]
    reg_config = payload[3]
    
    osrs_h    = (ctrl_hum >> 0) & 0b111    # bits 2:0
    osrs_t  = (ctrl_meas >> 5) & 0b111   # bits 7:5
    osrs_p  = (ctrl_meas >> 2) & 0b111   # bits 4:2
    mode    = (ctrl_meas >> 0) & 0b11    # bits 1:0
    t_sb  = (reg_config >> 5) & 0b111   # bits 7:5
    filter  = (reg_config >> 2) & 0b111   # bits 4:2
    spi3w_en    = (reg_config >> 0) & 0b1    # bit 0
    
    bme280_config.oversamp_hum = oversamp_d[osrs_h]
    bme280_config.oversamp_temp = oversamp_d[osrs_t]
    bme280_config.oversamp_press = oversamp_d[osrs_p]
    bme280_config.mode = mode_d[mode]
    bme280_config.t_sb = t_sb_d[t_sb]
    bme280_config.filter = filter_d[filter]
    bme280_config.spi3w_en = spi3w_en_d[spi3w_en]
   
def handleBME280_selection(sender, app_data):
    print(sender, app_data)
    info_txt=""
    
    match sender:
        case 237: # t_sb
            info_txt="Controls the time constant of the IIR filter. \r\nSee Table 27 for settings and chapter 3.4.4 for details"
        case 243: # SPI
            info_txt="The SPI interface has two modes: 4-wire and 3-wire. The protocol is the same for both. \r\nThe 3-wire mode is selected by setting '1' to the register spi3w_en. \r\nThe pad SDI is used as a data pad in 3-wire mode."
    
    dpg.configure_item("bme280_info_text", default_value=info_txt)
    
def init_window():         
    # BME280 window
    with dpg.child_window(width=settings.RIGHT_WINDOW_SIZE[0], height=settings.RIGHT_WINDOW_SIZE[1], pos=settings.RIGHT_WINDOW_POS, tag="right_window_bme280", show=False): 
                
        txt_bmewindow = dpg.add_text("BME280 Settings")   
        dpg.bind_item_font(txt_bmewindow, settings.large)  
        
        dpg.add_button(label="Get config from hardware", callback=get_bme280_config)
        dpg.add_text(" ")  
        
        with dpg.group(horizontal=True):
            dpg.add_text("ID")  
            dpg.add_input_text(width=100, default_value=f"{bme280_config.id}", tag="bme280_id")
            
        dpg.add_text(" ") 
        dpg.add_text("Temperature Oversampling")  
        dpg.add_combo(("Skipped (output set to 0x80000)", 
                       "Oversampling x 1", "Oversampling x 2", 
                       "Oversampling x 4", "Oversampling x 8", 
                       "Oversampling x 16"),width=200, default_value=bme280_config.oversamp_temp, tag="bme280_oversamp_temp")
        
        dpg.add_text("Pressure Oversampling")  
        dpg.add_combo(("Skipped (output set to 0x80000)", 
                       "Oversampling x 1", "Oversampling x 2", 
                       "Oversampling x 4", "Oversampling x 8", 
                       "Oversampling x 16"),width=200, default_value=bme280_config.oversamp_press, tag="bme280_oversamp_press")
        
        dpg.add_text("Humidity Oversampling")  
        dpg.add_combo(("Skipped (output set to 0x80000)", 
                       "Oversampling x 1", "Oversampling x 2", 
                       "Oversampling x 4", "Oversampling x 8", 
                       "Oversampling x 16"),width=200, default_value=bme280_config.oversamp_hum, tag="bme280_oversamp_hum")
        
        dpg.add_text(" ") 
        dpg.add_text("Mode")  
        dpg.add_combo(("Sleep mode", 
                       "Forced Mode", 
                       "Normal Mode"),width=200, default_value=bme280_config.mode, tag="bme280_mode")
        
        dpg.add_text(" ") 
        dpg.add_text("T_standby")  
        dpg.add_combo(("0.5", 
                       "10",
                       "20",
                       "62.5", 
                       "125", 
                       "250", 
                       "500", 
                       "1000"),width=200, default_value=bme280_config.t_sb, tag="bme280_t_sb")
        
        with dpg.group(horizontal=True):
            dpg.add_text("Filter")  
            dpg.add_button(label="?", callback=handleBME280_selection)
                    
        dpg.add_combo(("Filter off", 
                       "2",
                       "4",
                       "8", 
                       "16"),width=200, default_value=bme280_config.filter, tag="bme280_filter")
        
        
        with dpg.group(horizontal=True):
            dpg.add_text("SPI Wire")  
            dpg.add_button(label="?", callback=handleBME280_selection)
        dpg.add_combo(("3-wire", 
                        "4-wire"),width=200, default_value=bme280_config.spi3w_en, tag="bme280_spi3w_en")
        
      
        with dpg.child_window(width=settings.RIGHT_WINDOW_SIZE[0]-300, height=settings.RIGHT_WINDOW_SIZE[1], pos=[settings.RIGHT_WINDOW_POS[0]+300, 0], tag="right_window_bme280_info", show=True): 
            dpg.add_text(default_value="", tag="bme280_info_text")
            