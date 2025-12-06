import yaml
import os

# ---------------- CONFIG ----------------
yaml_file = "C:/Git/Hybrid/tools/buses/busDef.yaml"
arduino_sketch_dir = "C:/Git/Hybrid/tools/buses/main"
output_dir = os.path.join(arduino_sketch_dir, "src")
os.makedirs(output_dir, exist_ok=True)
# ---------------------------------------


def getReadSensorLines(sensorName):
    
    sensorFunction = {
        "NA":" ",
        "PWR":"void busPwrConfig::readSensor(){\n    sensor_battVolts = (analogRead(busPwr.battVolts.pin) * busPwr.battVolts.c1) + busPwr.battVolts.c1;\n    sensor_voltage3V = (analogRead(busPwr.voltage3V.pin) * busPwr.voltage3V.c1) + busPwr.voltage3V.c1;\n    sensor_voltage5V = (analogRead(busPwr.voltage5V.pin) * busPwr.voltage5V.c1) + busPwr.voltage5V.c1;\n}",
        "BME280":"void busBME280Config::readSensor(Adafruit_BME280& bme){\n    sensor_temperatureC = (bme.readTemperature() * busBME280.temperatureC.c1) + busBME280.temperatureC.c0;\n    sensor_pressurePasc = (bme.readPressure() * busBME280.pressurePasc.c1) + busBME280.pressurePasc.c0;\n    sensor_humidityRH   = (bme.readHumidity() * busBME280.humidityRH.c1) + busBME280.humidityRH.c0;\n    sensor_altitudeM    = (bme.readAltitude(1013.25) * busBME280.altitudeM.c1) + busBME280.altitudeM.c0;\n}"
    }
    
    sensorDef = {
        "NA":" ",
        "PWR":"    void readSensor();",
        "BME280":"    void readSensor(Adafruit_BME280& bme);"
    }
    return sensorFunction.get(sensorName), sensorDef.get(sensorName)
    
    
# Load YAML
with open(yaml_file, "r") as f:
    buses = yaml.safe_load(f)
    
for bus_name, bus_info in buses.items():
    print(bus_name)
    
    valuesLines = ""
    ifLines = ""
    #serializeInputLine = ""
    floatUn = ""
    floatVar=""
    buffer = ""
    readSensorH = ""
    sensorLines = ""
    readSensorLines = ""
    
    i=0
    buff_index = 0
    for field_name, field_props in bus_info['data'].items(): # look at each variable
        i=i+1
        #valuesLines += f"    {field_props.values()},\n"
        thisLine = "{"
        for index, value in enumerate(field_props.values()): # get properties of each variable
            if index == len(field_props.values())-1:
                thisLine += f" {value}}}"
            elif index == 1 or index == 2:
                thisLine += f' "{value}",'
            else:
                thisLine += f" {value},"
                
        if field_props['type'] == "float":
            floatUn += f"union {{float f;uint32_t u;}} {field_name}_u;\n    "
            floatVar += f"{field_name}_u.f = sensor_{field_name};\n    "
            tempName = field_name + "_u.u"
        else:
            tempName = "sensor_" + field_name
            
        # do bit math    
        if i == len(bus_info['data'].items()): # double indent if not the last one
            valuesLines += f"    {thisLine}"
            #serializeInputLine += f"{field_props['type']} {field_name}"
            if field_props['type'] == "float" or field_props['type'] == "uint32_t": # if float or 32bit int then split up into 4 bytes
                buffer += f"buffer[{buff_index}] = ({tempName} >> 24) & 0xFF; // Most significant byte (MSB)\n    buffer[{buff_index+1}] = ({tempName} >> 16) & 0xFF;\n    buffer[{buff_index+2}] = ({tempName} >> 8)  & 0xFF;\n    buffer[{buff_index+3}] = {tempName} & 0xFF;         // Least significant byte (LSB)"
                buff_index = buff_index+4
            elif field_props['type'] == "uint16_t": # if 16bit int then split up into 2 bytes
                buffer += f"buffer[{buff_index}] = ({tempName} >> 8) & 0xFF;  // High byte (bits 9-8)\n    buffer[{buff_index+1}] = {tempName} & 0xFF;         // Low byte (bits 7-0)"
                buff_index = buff_index+2
                                    
        else:
            valuesLines += f"    {thisLine},\n"
            #serializeInputLine += f"{field_props['type']} {field_name}, "
            if field_props['type'] == "float" or field_props['type'] == "uint32_t": # if float or 32bit int then split up into 4 bytes
                buffer += f"buffer[{buff_index}] = ({tempName} >> 24) & 0xFF; // Most significant byte (MSB)\n    buffer[{buff_index+1}] = ({tempName} >> 16) & 0xFF;\n    buffer[{buff_index+2}] = ({tempName} >> 8)  & 0xFF;\n    buffer[{buff_index+3}] = {tempName} & 0xFF;         // Least significant byte (LSB)\n\n    "
                buff_index = buff_index+4
            elif field_props['type'] == "uint16_t": # if 16bit int then split up into 2 bytes
                buffer += f"buffer[{buff_index}] = ({tempName} >> 8) & 0xFF;  // High byte (bits 9-8)\n    buffer[{buff_index+1}] = {tempName} & 0xFF;         // Low byte (bits 7-0)\n\n    "
                buff_index = buff_index+2    
                
        ifLines += f'   if (strcmp(fieldName, "{field_name}") == 0) return &{field_name};\n'
        
        # Sensor lines
        sensorLines += f"    {field_props['type']} sensor_{field_name}; \n"

    readSensorLines,readSensorH = getReadSensorLines(bus_info['sensorName'])


    # -------- busPwr.h ---------------------------------------------------------------------------------------------------------
    header_path = os.path.join(output_dir, bus_name + ".h")

    h_template = """
//This was autogenerated by generateBuses.py

#ifndef {ifndef}
#define {ifndef}

#include <Arduino.h>
#include <Adafruit_BME280.h>

struct {fieldConfig} {{
    int initVal;
    const char* unit;
    const char* type;
    int startByte;
    int bytes;
    int bits;
    double c0;
    double c1;
    uint32_t pin;
}};

struct {busConfig} {{
    int id;
    int size;
    int frequency;
    const char* sensorName;
    const char* endian;
{fieldConfigLines} 
{sensorLines}
    const {fieldConfig}* getField(const char* fieldName) const;
{readSensorH}
    std::array<uint8_t, {size}> serialize() const;
}};

extern {busConfig} {busName};

#endif

"""

    fieldConfigLines = ""
    for field_name, field_props in bus_info['data'].items():
        fieldConfigLines += f"    {bus_name + "FieldConfig"} {field_name};\n"
        
    output = h_template.format(
        busName=bus_name,
        ifndef=bus_name.upper() + "_H",
        fieldConfig=bus_name + "FieldConfig",
        busConfig=bus_name + "Config",
        fieldConfigLines=fieldConfigLines,
        size=bus_info['size'],
        sensorLines=sensorLines,
        readSensorH=readSensorH,
    )
    
    with open(header_path, "w") as f:
        f.write(output)


    # -------- busPwr.cpp ---------------------------------------------------------------------------------------------------------
    cpp_path = os.path.join(output_dir, bus_name + ".cpp")
    
    cpp_template = """
//This was autogenerated by generateBuses.py

#include {busdotH}
#include <string.h>
#include <Arduino.h>

{busConfig} {busName} = {{
    {id},
    {size},
    {freq},
    {endian},
    {sensorName},
{vals}
}};

const {fieldConfig}* {busConfig}::getField(const char* fieldName) const {{
{ifLines}
    return nullptr;
    
}}

{readSensor}

std::array<uint8_t, {size}> {busConfig}::serialize() const {{
    std::array<uint8_t, {size}> buffer{{}};
    buffer.fill(0);
    
    {floatUn}
    {floatVar}
    {buffer}
    
    return buffer;
}}


"""
 
    output = cpp_template.format(
        busName=bus_name,
        busdotH=f'"{bus_name}.h"',
        fieldConfig=bus_name + "FieldConfig",
        busConfig=bus_name + "Config",
        id=bus_info['id'],
        size=bus_info['size'],
        freq=bus_info['freq'],
        endian=f'"{bus_info['endian']}"',
        sensorName=f'"{bus_info['sensorName']}"',
        vals=valuesLines,
        ifLines=ifLines,
        #serializeInputLine=serializeInputLine,
        floatUn=floatUn,
        floatVar=floatVar,
        buffer=buffer,
        readSensor=readSensorLines,
    )
    with open(cpp_path, "w") as f:
        f.write(output)

    print(f"Generated files in Arduino sketch folder:\n- {header_path}\n- {cpp_path}")
