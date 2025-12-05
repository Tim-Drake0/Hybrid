#ifndef BUSBME280_H
#define BUSBME280_H

#include <Arduino.h>

struct BusBME280FieldConfig {
    int initVal;
    const char* unit;
    int startByte;
    int bytes;
    int bits;
    double c0;
    double c1;
};

struct BusBME280Config {
    int id;
    int size;
    int frequency; // Hz
    const char* endian;
    BusBME280FieldConfig temperatureC;
    BusBME280FieldConfig pressurePasc;
    BusBME280FieldConfig humidityRH;


    const BusBME280FieldConfig* getField(const char* fieldName) const;
    int bufferSize() const;
    void serialize(uint16_t* values, uint8_t* buffer) const;
};

extern const BusBME280Config busBME280;

#endif