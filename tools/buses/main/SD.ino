
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

    pinMode(CS_SD_pin, OUTPUT);
    digitalWrite(CS_SD_pin, HIGH);

    if(sd_present){
        if(SD.exists("test.txt")){
            SD.remove("test.txt");
        }

        myFile = SD.open("test.txt", FILE_WRITE);


        // might want to write some info at the top of the file, or maybe a separate config output file?


        // write data header line
        if (myFile) {
            myFile.println("time [ms], sensorBIT,battVolts, voltage3V, voltage5V......");
            //myFile.close();
        }
    }
}

void writeSDFrame(){
    // Only write if SD is present
    if(sd_present){
        if((thisFrame.currentMillis - SD_timeLastWrite) >= 1000 / SD_writeFreq){

            //myFile = SD.open("test.txt", FILE_WRITE);
            if (myFile) {

                myFile.print(thisFrame.currentMillis); myFile.print(", ");
                myFile.print(thisFrame.sensorsBIT); myFile.print(", ");
                myFile.print(thisFrame.battVolts); myFile.print(", ");
                myFile.print(thisFrame.voltage3V); myFile.print(", ");
                myFile.print(thisFrame.voltage5V); myFile.print(", ");

                myFile.print(thisFrame.temperatureC); myFile.print(", ");
                myFile.print(thisFrame.pressurePasc); myFile.print(", ");
                myFile.print(thisFrame.humidityRH); myFile.print(", ");
                myFile.print(thisFrame.altitudeM); myFile.print(", ");

                myFile.print(thisFrame.accelx); myFile.print(", ");
                myFile.print(thisFrame.accely); myFile.print(", ");
                myFile.print(thisFrame.accelz); myFile.print(", ");
                myFile.print(thisFrame.gyrox); myFile.print(", ");
                myFile.print(thisFrame.gyroy); myFile.print(", ");
                myFile.print(thisFrame.gyroz); myFile.print(", ");
                myFile.print(thisFrame.magx); myFile.print(", ");
                myFile.print(thisFrame.magy); myFile.print(", ");
                myFile.print(thisFrame.magz); myFile.print(", ");

                myFile.print(thisFrame.highG_accelx); myFile.print(", ");
                myFile.print(thisFrame.highG_accely); myFile.print(", ");
                myFile.print(thisFrame.highG_accelz); myFile.print(", ");



                myFile.println(" ");


                if((thisFrame.currentMillis - SD_timeLastFlush) >= 1000 * SD_flushFreq){
                    myFile.flush();
                }
                //myFile.close();

            }
            SD_timeLastWrite = thisFrame.currentMillis;
        }
    }
    // should update sensorBIT if not present
}



