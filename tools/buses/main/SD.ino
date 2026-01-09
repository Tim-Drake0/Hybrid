
#include "src/SensorDataFrame.h"

#include <Wire.h>
#include <Arduino.h>
#include <Adafruit_Sensor.h>

#include <SPI.h> 
#include <SD.h>



bool sd_present = false;


File myFile;

int SD_writeFreq = 20; // Hz
int SD_flushFreq = 5; // seconds
uint32_t SD_timeLastWrite = 0UL;
uint32_t SD_timeLastFlush = 0UL;

void beginSD(){
    if (SD.begin(CS_SD_pin)){
        bitSet(thisFrame.sensorsBIT, 4); 
        sd_present = true; 
    }

    if(sd_present){
        if(SD.exists("test.bin")){
            SD.remove("test.bin");
        }

        myFile = SD.open("test.bin", FILE_WRITE);

        // might want to write some info at the top of the file, or maybe a separate config output file?
    }
}

void writeSDFrame(){
    // Only write if SD is present
    if(sd_present){
        if((thisFrame.currentMillis - SD_timeLastWrite) >= 1000 / SD_writeFreq){

            if (myFile) {

                myFile.write((uint8_t*)&thisFrame, sizeof(thisFrame));

                if((thisFrame.currentMillis - SD_timeLastFlush) >= 1000 * SD_flushFreq){
                    myFile.flush();
                    SD_timeLastFlush = thisFrame.currentMillis;
                }
            }
            SD_timeLastWrite = thisFrame.currentMillis;
        }
    }
    // should update sensorBIT if not present
}



