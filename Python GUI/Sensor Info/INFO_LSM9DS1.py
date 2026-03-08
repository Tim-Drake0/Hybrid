import dearpygui.dearpygui as dpg
import serial_reader as sr
import serial_writer as sw
import time
import sys
from pathlib import Path
sensor_path = Path(__file__).parent.parent
sys.path.append(str(sensor_path))
import gui_settings as settings

CMD_GET_LSM9DS1_SETTINGS = 0x03

fs_g_d = {0:"245 dps", 1:"500 dps", 2:"N/A dps", 3:"2000 dps"}
lp_mode_d = {0:"enabled", 1:"disabled"}
hp_en_d = {0:"enabled", 1:"disabled"}    
fs_xl_d = {0:"±2g", 1:"±16g", 2:"±4g", 3:"±8g"}
bw_xl_d = {0:"408 Hz", 1:"211 Hz", 2:"105 Hz", 3:"50 Hz"}
     
class LSM9DS1Config:
    ag_id: int = 0x00
    fs_g: str = "N/A" # Gyroscope full-scale selection
    lp_mode: str = "N/A" # Low-power mode enable
    hp_en: str = "N/A" # High-pass filter enable
    fs_xl: str = "N/A" # Accelerometer full-scale selection
    bw_xl: str = "N/A" # Accelerometer anti-aliasing filter bandwidth selection
config = LSM9DS1Config()

def on_select(sender, app_data):
    dpg.set_value(sender, False)
    if app_data:
        settings.show_right_window("right_window_lsm9ds1")
        
def send_get_lsm9ds1_settings() -> bool:
    """Request packet containing current LSM9DS1 settings."""
    return sw._send(CMD_GET_LSM9DS1_SETTINGS)

def get_config():
    print("Getting lsm9ds1 config")
    send_get_lsm9ds1_settings()
    
    time.sleep(.5)
    
    dpg.set_value("lsm9ds1_id", f"{config.ag_id}")
    dpg.set_value("lsm9ds1_fs_g", f"{config.fs_g}")
    dpg.set_value("lsm9ds1_fs_xl", f"{config.fs_xl}")
    dpg.set_value("lsm9ds1_bw_xl", f"{config.bw_xl}")

def readSettings(payload):
    config.ag_id = f"{payload[0]:#04x}"
                        
    ctrl_reg1_g = payload[1]
    bw_g = (ctrl_reg1_g >> 0) & 0b11         # TODO
    fs_g = (ctrl_reg1_g >> 3) & 0b11 
    odr_g = (ctrl_reg1_g >> 5) & 0b111       # TODO
    
    ctrl_reg2_g = payload[2]                 # TODO
    ctrl_reg3_g = payload[3]
    
    hpcf_g = (ctrl_reg3_g >> 0) & 0b1111     # TODO
    hp_en = (ctrl_reg3_g >> 6) & 0b1
    lp_mode = (ctrl_reg3_g >> 7) & 0b1
    
    
    
    orient_cfg_g = payload[4]
    orient = (orient_cfg_g >> 0) & 0b111     # TODO
    signx_g = (orient_cfg_g >> 5) & 0b1      # TODO
    signy_g = (orient_cfg_g >> 4) & 0b1      # TODO
    signz_g = (orient_cfg_g >> 3) & 0b1      # TODO
    
    
    status_reg = payload[5]
    ig_xl = (status_reg >> 6) & 0b1          # TODO
    ig_g = (status_reg >> 5) & 0b1           # TODO
    inact = (status_reg >> 4) & 0b1          # TODO
    boot_status = (status_reg >> 3) & 0b1    # TODO
    tda = (status_reg >> 2) & 0b1            # TODO
    gda = (status_reg >> 1) & 0b1            # TODO
    xlda = (status_reg >> 0) & 0b1           # TODO
    
    
    
    ctrl_reg6_xl = payload[6]
    bw_xl = (ctrl_reg6_xl >> 0) & 0b11
    bw_scal_odr = (ctrl_reg6_xl >> 2) & 0b1  # TODO
    fs_xl = (ctrl_reg6_xl >> 3) & 0b11
    odr_xl = (ctrl_reg6_xl >> 5) & 0b111     # TODO
    
    ctrl_reg7_xl = payload[7]
    hpis1 = (ctrl_reg7_xl >> 0) & 0b1
    fds = (ctrl_reg7_xl >> 2) & 0b1
    dcf = (ctrl_reg7_xl >> 5) & 0b11
    hr = (ctrl_reg7_xl >> 7) & 0b1
    
    
    ctrl_reg8 = payload[8]
    sw_reset = (ctrl_reg8 >> 0) & 0b1        # TODO
    ble = (ctrl_reg8 >> 1) & 0b1             # TODO
    if_add_inc = (ctrl_reg8 >> 2) & 0b1      # TODO
    sim = (ctrl_reg8 >> 3) & 0b1             # TODO
    pp_od = (ctrl_reg8 >> 4) & 0b1           # TODO
    h_active = (ctrl_reg8 >> 5) & 0b1        # TODO
    bdu = (ctrl_reg8 >> 6) & 0b1             # TODO
    boot = (ctrl_reg8 >> 7) & 0b1            # TODO
    
    
    ctrl_reg9 = payload[9]                   # TODO
    stop_on_fth =  (ctrl_reg9 >> 0) & 0b1    # TODO
    fifo_en =  (ctrl_reg9 >> 1) & 0b1        # TODO
    i2c_disable =  (ctrl_reg9 >> 2) & 0b1    # TODO
    drdy_mask_bit =  (ctrl_reg9 >> 3) & 0b1  # TODO
    fifo_temp_en =  (ctrl_reg9 >> 4) & 0b1   # TODO
    sleep_g =  (ctrl_reg9 >> 6) & 0b1        # TODO
    
    config.fs_g = fs_g_d[fs_g]
    config.lp_mode = lp_mode_d[lp_mode]
    config.hp_en = hp_en_d[hp_en]
    config.fs_xl = fs_xl_d[fs_xl]
    config.bw_xl = bw_xl_d[bw_xl]
    
def init_window():
    # LSM9DS1 window
    with dpg.child_window(width=settings.RIGHT_WINDOW_SIZE[0], height=settings.RIGHT_WINDOW_SIZE[1], pos=settings.RIGHT_WINDOW_POS, tag="right_window_lsm9ds1", show=False): 
                
        txt_lsm9ds1window = dpg.add_text("LSM9DS1 Settings") 
        dpg.bind_item_font(txt_lsm9ds1window, settings.large)  
        
        dpg.add_button(label="Get config from hardware", callback=get_config)
        dpg.add_text(" ")  
        
        with dpg.group(horizontal=True):
            dpg.add_text("ID")  
            dpg.add_input_text(width=100, default_value=f"{config.ag_id}", tag="lsm9ds1_id")

        dpg.add_text(" ") 
        dpg.add_text("Gyroscope full-scale selection")  
        dpg.add_combo(("N/A dps", 
                       "245 dps", 
                       "500 dps",  
                       "2000 dps"),width=200, default_value=config.fs_g, tag="lsm9ds1_fs_g")
        
        dpg.add_text(" ") 
        dpg.add_text("Accelerometer full-scale selection")  
        dpg.add_combo(("±2g", 
                       "±4g", 
                       "±6g",  
                       "±8g"),width=200, default_value=config.fs_xl, tag="lsm9ds1_fs_xl")
        
        dpg.add_text(" ") 
        dpg.add_text("Accelerometer anti-aliasing filter bandwidth selection")  
        dpg.add_combo(("50 Hz", 
                       "105 Hz", 
                       "211 Hz",  
                       "408 Hz"),width=200, default_value=config.bw_xl, tag="lsm9ds1_bw_xl")            
    
