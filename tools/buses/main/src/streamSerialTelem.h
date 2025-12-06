
#ifndef STREAMSERIALTELEM_H
#define STREAMSERIALTELEM_H
#include <Arduino.h>
#include "busPwr.h"
#include "busBME280.h"


struct streamSerialTelemConfig {
    int id;
    int size;
    int frequency;
    busPwrConfig busPwr;
    busBME280Config busBME280;
};

#endif