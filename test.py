#!/bin/env python3
#coding=ASCII

import inspect
import itertools
import time
import types
import signal
import numpy as np
import datetime
import time
import statistics
import telnetlib    # for communication with ammeter
from labjack import ljm    # for communication with LabJack
import os


import venus_data_utils.venusplc as venusplc
        
venus = venusplc.VENUSController(read_only=True)

# set directory to save csds
directory = "/home/rehak/csds/"

############## stuff to set up faster Ammeter
measurementFrequency = 1000

def sendCommand(connection,command):
    connection.write((command+'\n').encode('ascii'))

def setupSystem(verbose=0):
    IP = "10.10.100.75"
    port = 5024

    # Connect to Ammeter
    if verbose:   print('attempt to connect...')
    connection = telnetlib.Telnet(IP,port,timeout = 3)
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

def getCurrent(connection):
    sendCommand(connection,":meas:curr?")
    return float(connection.read_until(b'\n').decode("ascii")[-15:-2])

connection = setupSystem(verbose=0)

################ done setting up faster Ammeter
################ stuff to set up LabJack

handle = ljm.openS("T8","usb","ANY")

def getB():
    B = ljm.eReadName(handle,"AIN0")
    return(B*0.4)     # hall probe has 2 T as 5 V

def setBatman(current):
    ljm.eWriteName(handle,"DAC0",current*.04)

################  done setting up Labjack


###  done with CSD functions
connection.close()   # close connnection to Ammeter
ljm.close(handle)    # close connection to labjack

