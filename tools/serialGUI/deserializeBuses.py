import serial_reader as sr
import struct

# ---------------- HELPERS ----------------
def bytes2Num(packet, startByte, bytes):
    if bytes == 2:
        return (packet[startByte] << 8) | packet[startByte+1]
    if bytes == 4:
        return (packet[startByte] << 24) | (packet[startByte+1] << 16) | (packet[startByte+2] << 8) | packet[startByte+3]
    
def bytes2Volts(packet, startByte):
    raw_volts = (packet[startByte] << 8) | packet[startByte+1]
    return (raw_volts / 1024) * 3.3

def bytes2Float(packet, startByte):
    raw_bytes = bytes(packet[startByte:startByte+4])
    return struct.unpack('>f', raw_bytes)[0]



class BusPwr:
    timestamp: int = 0
    id: int = 6910
    size: int = 14
    packetsSent: int = 0
    battVolts: float = 0
    voltage3V: float = 0
    voltage5V: float = 0
    
    def readBuffer(self, packet, idx):
        self.id             = bytes2Num(packet, idx, 2);    idx += 2
        self.timestamp      = bytes2Num(packet, idx, 4);    idx += 4
        self.packetsSent    = bytes2Num(packet, idx, 2);    idx += 2
        self.battVolts      = bytes2Volts(packet, idx);     idx += 2
        self.voltage3V      = bytes2Volts(packet, idx);     idx += 2
        self.voltage5V      = bytes2Volts(packet, idx);     idx += 2
        
class BusBME280:
    timestamp: int = 0
    id: int = 6911
    size: int = 24
    packetsSent: int = 0
    temperatureC: float = 0
    pressurePasc: float = 0
    humidityRH: float = 0
    altitudeM: float = 0
    
    def readBuffer(self, packet, idx):
        self.id             = bytes2Num(packet, idx, 2);    idx += 2
        self.timestamp      = bytes2Num(packet, idx, 4);    idx += 4
        self.packetsSent    = bytes2Num(packet, idx, 2);    idx += 2
        self.temperatureC   = bytes2Float(packet, idx);     idx += 4
        self.pressurePasc   = bytes2Float(packet, idx);     idx += 4
        self.humidityRH     = bytes2Float(packet, idx);     idx += 4
        self.altitudeM      = bytes2Float(packet, idx);     idx += 4
            
class BusLSM9DS1:
    timestamp: int = 0
    id: int = 6912
    size: int = 44
    packetsSent: int = 0
    accelx: float = 0
    accely: float = 0
    accelz: float = 0
    accelLSB: float = 0.00122; # 2G = 0.00061, 4G = 0.00122, 8G = 0.00244, 16G = 0.00732
    magx: float = 0
    magy: float = 0
    magz: float = 0
    magLSB: float = 0.00014; # 4GAUSS = 0.00014, 8GAUSS = 0.00029, 12GAUSS = 0.00043, 16GAUSS = 0.00058
    gyrox: float = 0
    gyroy: float = 0
    gyroz: float = 0
    gyroLSB: float = 0.07000; # 245DPS = 0.00875, 500DPS = 0.01750, 2000DPS = 0.07000
    
    def readBuffer(self, packet, idx):
        self.id             = bytes2Num(packet, idx, 2);                    idx += 2
        self.timestamp      = bytes2Num(packet, idx, 4);                    idx += 4
        self.packetsSent    = bytes2Num(packet, idx, 2);                    idx += 2
        self.accelx         = bytes2Float(packet, idx) * self.accelLSB;     idx += 4
        self.accely         = bytes2Float(packet, idx) * self.accelLSB;     idx += 4
        self.accelz         = bytes2Float(packet, idx) * self.accelLSB;     idx += 4
        self.magx           = bytes2Float(packet, idx) * self.magLSB;       idx += 4
        self.magy           = bytes2Float(packet, idx) * self.magLSB;       idx += 4
        self.magz           = bytes2Float(packet, idx) * self.magLSB;       idx += 4
        self.gyrox          = bytes2Float(packet, idx) * self.gyroLSB;      idx += 4
        self.gyroy          = bytes2Float(packet, idx) * self.gyroLSB;      idx += 4
        self.gyroz          = bytes2Float(packet, idx) * self.gyroLSB;      idx += 4
        
class BusADXL375:
    timestamp: int = 0
    id: int = 6913
    packetsSent: int = 0
    highG_accelx: float = 0
    highG_accely: float = 0
    highG_accelz: float = 0
    
class StreamTelem:
    header: int = 43962
    timestamp: int = 0
    id: int = 6900
    size: int = 111
    packetsSent: int = 0
    packet: int = [0] * size
    sensorsBIT: int = 0
        
    def find_and_read_packet(self):
        # maybe add timeout to this>
        
        while True:
            thisPacket = sr.ser.read(self.size)
            
            if len(thisPacket) != self.size:
                continue
            
            if (thisPacket[0] != (self.header >> 8) & 0xFF or thisPacket[1] != self.header & 0xFF 
            or thisPacket[2] != (self.id >> 8) & 0xFF or thisPacket[3] != self.id & 0xFF):
                print(f"{thisPacket[0]:02X}, {thisPacket[1]:02X}")
                continue
            
            self.packet = thisPacket
            return
    