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
        
venus = venusplc.VENUSController(read_only=False)

# set directory to save csds
directory = "/data/csds/"

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

################  set up stuff for CSDs

dipolealpha = 0.00823

if not os.path.exists("csds"):
    os.makedirs("csds")
if not os.path.exists(directory):
    os.makedirs(directory)


def datasheet(tst_str):
    readvars = venus.read_vars()
    with open(directory+'/dsht_'+tst_str,'w') as f:
        for i in range(len(readvars)):  
            f.write("%4i %.5e %s\n"%(i,venus.read([readvars[i]]),readvars[i]))

def get_csd(Ilow,Ihigh,npoints,wasin,tstarted):
    Vext = venus.read(['extraction_v'])
    Bstart = getB()
    Istart = venus.read(['batman_i_set'])/131.0   
    
    changeslow(Istart,Ilow,twait=1)
    if wasin == 0:
        morewaittime = tstarted + 10. - time.time()
        if morewaittime > 0:
            if morewaittime>10:   # add this as a safety catch.  Shouldn't happen
                print(f'morewaittime > 10!! {morewaittime:.2f}')
                time.sleep(10)
            else:
                time.sleep(morewaittime)   

    batmanfield = np.zeros(npoints)
    faradaycup = np.zeros(npoints)
    timesteps = np.zeros(npoints)

    ipoints = np.sqrt(np.linspace(Ilow*Ilow,Ihigh*Ihigh,npoints))
    for i in range(npoints):
        setBatman(ipoints[i])
        faradaycup[i] = getCurrent(connection)
        batmanfield[i] = getB()
        timesteps[i] = time.time()

    if wasin == 0:
        venus.write({'fcv1_in':False}) # Take Faraday cup back out if it was out before start
    changeslow(ipoints[-1],Istart,twait=0)
    resetbatman(Bstart,Istart)

    # add search to peak beam here
    return(timesteps,ipoints,batmanfield,faradaycup)

def resetbatman(bgoal,Istart):
    tstart = time.time()

    #with open('temptemp','w') as f:
    if 1:
        Inew = Istart
        while time.time()<tstart+7.5:
            bnow = getB()
            if bnow<bgoal:
                Inew = Inew + 0.007
            elif bnow>bgoal:
                Inew = Inew - 0.007
            #f.write(f"{time.time()-tstart:7.4f} {Inew:10.3f} {bnow*1e5:10.3f} {1e6*getCurrent(connection):10.3f}\n")
            setBatman(Inew)
    if 0:   # Use this to make final steps if determined necessary
        Inew = Inew + 0.0
        setBatman(Inew)

def changeslow(istart,iend,twait=1):
    ipts = np.linspace(istart,iend,int(np.ceil(np.abs(istart-iend)))*3)
    for ipt in ipts:
        setBatman(ipt)
        iNow = getCurrent(connection)   # doing this to slow the process
        Bnow = getB()                   # doing this to slow the process
    time.sleep(twait)

def quickave(num=30):
    tot = 0
    for i in range(num):
        tot = tot + getCurrent(connection)
    return(tot/(num*1.))

def performFastCSD():
    # take a datasheet and a csd
    tallstart = time.time()
    tnowstr = str(int(time.time()))
    wasin = 1
    if not venus.read(['fcv1_in']):   # checking if faraday cup is in
        venus.write({'fcv1_in':True}) # if not, put it in
        wasin = 0                     # set wasin to zero.  Will have to wait ~10 s to start CSD
    datasheet(tnowstr)

    alpha = 0.00824    # calculated...need notes DST
    m = 79e-5          # slope of linear fit of B vs I...need notes DST
    Vext = venus.read({'extraction_v'})
    Ilow = alpha/m*np.sqrt(0.84*Vext)
    Ihigh = alpha/m*np.sqrt(8.9*Vext)
    with open(directory+'/csd_'+tnowstr,'w') as outfile:
        timesteps, ipoints, batmanfield, faradaycup = get_csd(Ilow,Ihigh,1200,wasin,tallstart)           
        for i in range(len(timesteps)):
            outfile.write("%.3f %.3f %.8f %.5e\n"%(timesteps[i],ipoints[i],batmanfield[i],faradaycup[i]))
    tnow = time.time()
    nowdt = datetime.datetime.now()
    formatted_time = nowdt.strftime("%Y-%m-%d %H:%M:%S")
    with open(directory+'log','a') as f:
        f.write(f'{formatted_time} CSD time = {time.time()-tallstart:.1f}\n')
    print(f'{formatted_time} CSD time = {time.time()-tallstart:.1f}')


#reset just in case
venus.write({'csd_in_progress':0})


again = 1
ibatmanlast = venus.read(['batman_i'])
doCSD = 0
treadagain = time.time()
tlastave = time.time()
while again:
    nmeas = 0.
    iave = 0.
    isq = 0.
    while time.time()-tlastave < 0.33:
        nmeas = nmeas + 1
        inow = getCurrent(connection)
        iave = iave + inow
        isq = isq + inow*inow

        # check for batman requests
        ibatmanrequest = venus.read(['batman_i_set'])/131.0
        if ibatmanrequest != ibatmanlast:
            if ibatmanrequest > (ibatmanlast + 1) or ibatmanrequest < (ibatmanlast - 1):
                changeslow(ibatmanlast,ibatmanrequest,twait=0)
            else:
                setBatman(ibatmanrequest)
            ibatmanlast = ibatmanrequest
    tlastave = time.time()
    iave = iave/(nmeas)
    isq = isq/(nmeas)
    istd = np.sqrt( isq - iave*iave )
    venus.write({'fcv1_ammeter':iave})
    if iave==0:
        venus.write({'fcv1_ammeter_stdev':-2.})
    else:
        venus.write({'fcv1_ammeter_stdev':istd/iave*100.})

    if venus.read(['csd_request']):
        venus.write({'csd_in_progress':1})
        venus.write({'fcv1_ammeter':0})
        venus.write({'fcv1_ammeter_stdev':0.})
        performFastCSD()
        venus.write({'csd_in_progress':0})
        doCSD = 0
        tlastave = time.time()
        ibatmanrequest = venus.read(['batman_i_set'])/131.0   # new V3
    if time.time()-treadagain >= 5:
        with open('again','r') as f:
            again = int(f.readline())
        treadagain = time.time()
        tlastave = time.time()

###  done with CSD functions
connection.close()   # close connnection to Ammeter
ljm.close(handle)    # close connection to labjack

