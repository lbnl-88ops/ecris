import time
import numpy as np

class VenusDummy:
    def write(self, data):
        print(f'VENUS WRITE: {data}')

venus = VenusDummy()

def sendCommand(connection,command):
    connection.write((command+'\n').encode('ascii'))

def getCurrent(connection):
    sendCommand(connection,":meas:curr?")
    return float(connection.read_until(b'\n').decode("ascii")[-15:-2])

def legacy_current_measurement(connection):
    nmeas = 0.
    iave = 0.
    isq = 0.
    tlastave = time.time()
    while time.time()-tlastave < 0.33:
        nmeas = nmeas + 1
        inow = getCurrent(connection)
        iave = iave + inow
        isq = isq + inow*inow
    iave = iave/(nmeas)
    isq = isq/(nmeas)
    istd = np.sqrt( isq - iave*iave )
    venus.write({'fcv1_ammeter':iave})