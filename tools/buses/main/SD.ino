
#include "src/SensorDataFrame.h"

#include <Wire.h>
#include <Arduino.h>
#include <Adafruit_Sensor.h>

#include <SPI.h> 
#include <SdFat.h>

#define MAX_FILE_INDEX 999

SdFat SD;

bool sd_present = false;


File dataFile;

int SD_writeFreq = 30; // Hz
int SD_flushFreq = 5; // seconds
uint32_t SD_timeLastWrite = 0UL;
uint32_t SD_timeLastFlush = 0UL;
char flightDir[16];    // "flight999" + \0
char dataFileName[32];    // "flight999/data.bin"

void beginSD(){
    if (SD.begin(CS_SD_pin)){
        sd_present = true; 
    }

    File root = SD.open("/");
    root.close();


    if(sd_present){
        // might want to write some info at the top of the file, or maybe a separate config output file?
        readEEPROM();

        if (!findNextFlightDir()) {
            MySerial.println("No free flight directories");
            return;
        }
        MySerial.print("Making flight directory: "); MySerial.println(flightDir);

        if (!SD.mkdir(flightDir)) {
            MySerial.println("Failed to create flight dir");
            return;
        }

        snprintf(dataFileName, sizeof(dataFileName), "%s/data.bin", flightDir);

        dataFile = SD.open(dataFileName, FILE_WRITE);

        if (!dataFile) {
            MySerial.println("Failed to create data file!");
        } else {
            // Set bit only when SD present and found valid file
            bitSet(thisFrame.sensorsBIT, 4); 
            MySerial.print("Logging to: ");
            MySerial.println(dataFileName);
            dataFile.flush();   // force FAT entry to appear
        }
    }
}

void writeSDFrame(){
    // Only write if SD is present
    if(sd_present){
        if((thisFrame.currentMillis - SD_timeLastWrite) >= 1000 / SD_writeFreq){

            if (dataFile) {

                dataFile.write((uint8_t*)&thisFrame, sizeof(thisFrame));

                if((thisFrame.currentMillis - SD_timeLastFlush) >= 1000 * SD_flushFreq){
                    dataFile.flush();
                    SD_timeLastFlush = thisFrame.currentMillis;
                }
            }
            SD_timeLastWrite = thisFrame.currentMillis;
        }
    }
    // should update sensorBIT if not present
}

bool findNextFlightDir() {
    for (int i = 1; i <= 999; i++) {
        snprintf(flightDir, sizeof(flightDir), "/flight%03d", i);

        if (!SD.exists(flightDir)) {
            return true;   // flightDir now holds free directory name
        }
    }
    return false;  // card is full
}




