
#include "streamSerialTelem.h"
#include "busPwr.h"
#include "busBME280.h"

const streamSerialTelemConfig streamSerialTelem = {
    6900,
    6,
    50,
    busPwr,
    busBME280
};