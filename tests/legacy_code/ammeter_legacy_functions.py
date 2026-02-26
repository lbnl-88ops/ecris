import time
from typing import List

import numpy as np


class Telnet:
    def __init__(ip, port, timeout):
        pass
    def read_until(self, data):
        pass

class VenusDummy:
    def write(self, data):
        print(f'VENUS WRITE: {data}')
    def read_vars(self) -> List[str]:
        return []
    def read(self, str) -> float:
        return 0

# set directory to save csds
directory = "/data/csds/"

venus = VenusDummy()
measurementFrequency = 0

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
    if iave==0:
        venus.write({'fcv1_ammeter_stdev':-2.})
    else:
        venus.write({'fcv1_ammeter_stdev':istd/iave*100.})

def setupSystem(verbose=0):
    IP = "10.10.100.75"
    port = 5024

    # Connect to Ammeter
    if verbose:   print('attempt to connect...')
    connection = Telnet(IP,port,timeout = 3)
    output = connection.read_until(b'\n')
    if verbose:   print('connected.  Output: ',output,'\nResetting system')

    # Reset System
    sendCommand(connection,"*rst")
    if verbose:   print('reset')
    time.sleep(2)
    if verbose:   print('waited 2 seconds, setting up current reading')

    # Setting up reading settings
    sendCommand(connection,':sens:func "curr"')
    sendCommand(connection,':sens:curr:rang:auto on')
    sendCommand(connection,':sens:curr:nplc:auto off')

    # Set integration time in terms of wall frequency: MeasTime*^60Hz
    nplc = 1./measurementFrequency*60.0
    sendCommand(connection,':sens:curr:nplc '+str(nplc))

    # turn on input switch
    sendCommand(connection,':inp on')

    return connection

def datasheet(tst_str):
    readvars = venus.read_vars()
    with open(directory+'/dsht_'+tst_str,'w') as f:
        for i in range(len(readvars)):
            f.write("%4i %.5e %s\n"%(i,venus.read([readvars[i]]),readvars[i]))
