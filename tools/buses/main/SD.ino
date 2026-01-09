
#include "src/SensorDataFrame.h"

#include <Wire.h>
#include <Arduino.h>
#include <Adafruit_Sensor.h>

#include <SPI.h> 
#include <SD.h>

#define MAX_FILE_INDEX 999

bool sd_present = false;


File myFile;

int SD_writeFreq = 30; // Hz
int SD_flushFreq = 5; // seconds
uint32_t SD_timeLastWrite = 0UL;
uint32_t SD_timeLastFlush = 0UL;
char filename[10];

void beginSD(){
    if (SD.begin(CS_SD_pin)){
        sd_present = true; 
    }

    if(sd_present){
        
        strcpy(filename, "data.bin"); // base filename
        if (SD.exists(filename)) {
            bool found = false;
            for (int i = 1; i <= MAX_FILE_INDEX; i++) {
                sprintf(filename, "data%03d.bin", i);
                if (!SD.exists(filename)) {
                    found = true;
                    break; // found a free filename
                }
            }
            if (!found) {
                return;
            }
        }

        // Set bit only when SD present and found valid file
        bitSet(thisFrame.sensorsBIT, 4); 

        // might want to write some info at the top of the file, or maybe a separate config output file?

        myFile = SD.open(filename, FILE_WRITE | O_CREAT | O_EXCL);
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



