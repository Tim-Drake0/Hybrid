
#include "src/SensorDataFrame.h"

#include <Wire.h>
#include <Arduino.h>
#include <Adafruit_Sensor.h>

#include <SPI.h> 
#include <SD.h>

#define MAX_FILE_INDEX 999

bool sd_present = false;


File myFile;

int SD_writeFreq = 20; // Hz
int SD_flushFreq = 5; // seconds
uint32_t SD_timeLastWrite = 0UL;
uint32_t SD_timeLastFlush = 0UL;
char filename[32];

void beginSD(){
    if (SD.begin(CS_SD_pin)){
        bitSet(thisFrame.sensorsBIT, 4); 
        sd_present = true; 
    }

    if(sd_present){
        
        strcpy(filename, "datalog.bin"); // base filename
        if(SD.exists(filename)){
            for (int i = 1; i <= MAX_FILE_INDEX; i++) {
                sprintf(filename, "datalog%03d.bin", i);
                if (!SD.exists(filename)) {
                    break; // found a free filename
                }
            }
        }

        myFile = SD.open(filename, FILE_WRITE);

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



